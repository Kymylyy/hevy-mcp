from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from statistics import mean, median
from typing import Any

from ..analytics import fatigue_risk_level
from ..errors import NoDataError
from ..response import ToolResult, build_result
from ..service import HevyService
from ..utils import estimate_e1rm, format_number, is_working_set, parse_iso_datetime, utc_now


def fatigue_check(service: HevyService) -> ToolResult:
    now = utc_now()
    start = now - timedelta(days=21)
    workouts = service.client.get_workouts_since(start)
    if not workouts:
        raise NoDataError(
            "No recent workouts available for fatigue analysis.",
            "Log more sessions and run fatigue_check again.",
        )

    lift_keywords = {
        "squat": ("squat",),
        "hinge": ("deadlift", "rdl"),
        "press": ("bench", "press"),
        "row": ("row",),
        "vertical_pull": ("pulldown", "pull up", "pull-up", "chin"),
    }
    exposures: defaultdict[str, list[float]] = defaultdict(list)

    recent_cutoff = now - timedelta(days=7)
    recent_failure = recent_working = 0
    prior_failure = prior_working = 0
    workout_dates = []

    sorted_workouts = sorted(
        workouts,
        key=lambda row: parse_iso_datetime(str(row.get("start_time"))),
    )
    for workout in sorted_workouts:
        start_raw = workout.get("start_time")
        if not isinstance(start_raw, str):
            continue
        start_at = parse_iso_datetime(start_raw)
        workout_dates.append(start_at.date())
        bucket_recent = start_at >= recent_cutoff

        for exercise in workout.get("exercises", []):
            if not isinstance(exercise, dict):
                continue
            title = str(exercise.get("title", "")).lower()
            lift = ""
            for candidate, keywords in lift_keywords.items():
                if any(keyword in title for keyword in keywords):
                    lift = candidate
                    break

            sets = exercise.get("sets", [])
            if not isinstance(sets, list):
                continue
            top_set = 0.0
            for set_row in sets:
                if not isinstance(set_row, dict) or not is_working_set(set_row.get("type")):
                    continue
                if bucket_recent:
                    recent_working += 1
                    if set_row.get("type") == "failure":
                        recent_failure += 1
                else:
                    prior_working += 1
                    if set_row.get("type") == "failure":
                        prior_failure += 1

                e1rm = estimate_e1rm(set_row.get("weight_kg"), set_row.get("reps"))
                if e1rm is not None:
                    top_set = max(top_set, e1rm)
            if lift and top_set > 0:
                exposures[lift].append(top_set)

    signals: list[str] = []
    affected: list[str] = []

    for lift, values in exposures.items():
        if len(values) < 4:
            continue
        recent_values = values[-3:]
        baseline = values[:-3][-3:] if len(values) > 3 else values[:-3]
        if not baseline:
            continue
        baseline_avg = mean(baseline)
        recent_avg = mean(recent_values)
        if baseline_avg > 0 and (recent_avg - baseline_avg) / baseline_avg <= -0.05:
            signals.append("performance_drop")
            affected.append(lift)

    prior_ratio = (prior_failure / prior_working) if prior_working else 0.0
    recent_ratio = (recent_failure / recent_working) if recent_working else 0.0
    ratio_increase = recent_ratio - prior_ratio
    if recent_working >= 3 and (
        (
            prior_ratio > 0
            and recent_ratio >= prior_ratio * 1.3
            and ratio_increase >= 0.1
        )
        or (prior_ratio == 0 and recent_ratio >= 0.3)
    ):
        signals.append("effort_creep")

    unique_dates = sorted(set(workout_dates))
    if len(unique_dates) >= 4:
        gaps = [
            float((unique_dates[i] - unique_dates[i - 1]).days)
            for i in range(1, len(unique_dates))
        ]
        baseline_gap = median(gaps[:-1]) if len(gaps) > 1 else gaps[0]
        latest_gap = gaps[-1]
        if baseline_gap > 0 and latest_gap > baseline_gap * 1.5:
            signals.append("frequency_drop")

    risk = fatigue_risk_level(len(signals))
    confidence = "high" if len(sorted_workouts) >= 8 else "low"
    details = [f"- Triggered signals: {', '.join(signals) if signals else 'none'}"]
    if affected:
        details.append(f"- Affected lifts: {', '.join(sorted(set(affected)))}")
    details.append(f"- Recent failure ratio: {format_number(recent_ratio * 100, 1)}%")
    details.append(f"- Prior failure ratio: {format_number(prior_ratio * 100, 1)}%")

    notes = [
        "- Not medical advice. Treat this as a training-signal heuristic.",
        f"- Confidence: {confidence} (based on recent data volume).",
    ]
    if risk == "high":
        notes.append("- Consider a short deload or temporary intensity reduction.")
    elif risk == "moderate":
        notes.append("- Consider trimming failure sets for 1-2 sessions.")
    else:
        notes.append("- Current fatigue signal looks manageable.")

    data: dict[str, Any] = {
        "window": {
            "start_date": str(start.date()),
            "end_date": str(now.date()),
        },
        "risk": risk,
        "confidence": confidence,
        "signals": signals,
        "affected_lifts": sorted(set(affected)),
        "recent_failure_ratio": recent_ratio,
        "prior_failure_ratio": prior_ratio,
        "recent_working_sets": recent_working,
        "prior_working_sets": prior_working,
        "recent_failure_sets": recent_failure,
        "prior_failure_sets": prior_failure,
        "workout_count": len(sorted_workouts),
    }
    return build_result(
        f"Fatigue risk level: {risk}.",
        f"{start.date()} to {now.date()}",
        details,
        notes,
        data=data,
    )
