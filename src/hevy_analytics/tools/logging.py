from __future__ import annotations

from collections import Counter
from datetime import timedelta
from statistics import mean, median
from typing import Any

from ..errors import NoDataError
from ..response import ToolResult, build_result
from ..service import HevyService
from ..utils import format_number, parse_iso_datetime, utc_now
from ..validation import validate_days
from ._shared import split_label


def training_log(service: HevyService, days: int = 30) -> ToolResult:
    requested_days = validate_days(days)
    now = utc_now()
    start = now - timedelta(days=requested_days)
    workouts = service.client.get_workouts_since(start)
    if not workouts:
        raise NoDataError(
            "No workouts found in the requested period.",
            "Increase days and rerun training_log.",
        )

    ordered = sorted(workouts, key=lambda row: parse_iso_datetime(str(row.get("start_time"))))
    dates = [parse_iso_datetime(str(row.get("start_time"))).date() for row in ordered]
    gaps = [float((dates[i] - dates[i - 1]).days) for i in range(1, len(dates))]
    avg_gap = mean(gaps) if gaps else 0.0
    med_gap = median(gaps) if gaps else 0.0

    sessions_per_week = len(ordered) / max(requested_days / 7.0, 0.01)
    splits: Counter[str] = Counter()
    fallback = 0
    for workout in ordered:
        label = split_label(str(workout.get("title", "")))
        splits[label] += 1
        if label == "Other":
            fallback += 1

    details = [f"- {name}: {count}" for name, count in splits.items()]
    details.append(f"- Average gap between sessions: {format_number(avg_gap, 1)} days")
    details.append(f"- Median gap between sessions: {format_number(med_gap, 1)} days")

    summary = (
        f"{len(ordered)} sessions in last {requested_days} day(s) "
        f"({format_number(sessions_per_week, 2)} sessions/week)."
    )
    notes = [f"- Split classifier fallback used on {fallback} workout title(s)."]
    data: dict[str, Any] = {
        "window": {
            "days": requested_days,
            "start_date": str(start.date()),
            "end_date": str(now.date()),
        },
        "session_count": len(ordered),
        "sessions_per_week": sessions_per_week,
        "split_counts": dict(splits),
        "average_gap_days": avg_gap,
        "median_gap_days": med_gap,
        "fallback_count": fallback,
    }
    return build_result(summary, f"{start.date()} to {now.date()}", details, notes, data=data)
