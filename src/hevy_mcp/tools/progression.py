from __future__ import annotations

from datetime import timedelta
from typing import Any

from ..analytics import classify_trend
from ..errors import NoDataError, NotFoundError
from ..response import render_response
from ..service import HevyService
from ..utils import (
    estimate_e1rm,
    format_number,
    format_set,
    is_working_set,
    parse_iso_datetime,
    utc_now,
)
from ..validation import validate_name, validate_weeks


def exercise_progression(service: HevyService, name: str, weeks: int = 12) -> str:
    query = validate_name(name)
    requested_weeks = validate_weeks(weeks)
    matches = service.rank_templates(query)
    if not matches:
        raise NotFoundError(
            f"No exercise found for '{query}'.",
            "Use search_exercise first to confirm template naming.",
        )

    selected = matches[0]
    template_id = str(selected.get("id", ""))
    history = service.load_history(template_id)
    if not history:
        raise NoDataError(
            f"No exercise history available for {selected.get('title', template_id)}.",
            "Log at least one workout for this exercise and retry.",
        )

    now = utc_now()
    start = now - timedelta(weeks=requested_weeks)
    filtered: list[dict[str, Any]] = []
    for row in history:
        start_raw = row.get("workout_start_time")
        if not isinstance(start_raw, str):
            continue
        if parse_iso_datetime(start_raw) < start:
            continue
        if not is_working_set(row.get("set_type")):
            continue
        if row.get("weight_kg") is None and row.get("reps") is None:
            continue
        filtered.append(row)

    if not filtered:
        raise NoDataError(
            "No working sets found in the requested time window.",
            "Increase weeks or choose another exercise.",
        )

    service.load_workout_descriptions_since(start)

    sessions: dict[str, dict[str, Any]] = {}
    for row in filtered:
        workout_id = str(row.get("workout_id", "unknown-workout"))
        bucket = sessions.setdefault(
            workout_id,
            {
                "title": row.get("workout_title", "Workout"),
                "start": parse_iso_datetime(str(row.get("workout_start_time"))),
                "workout_id": workout_id,
                "sets": [],
            },
        )
        bucket["sets"].append(row)

    ordered = sorted(sessions.values(), key=lambda item: item["start"])
    session_best_e1rm: list[float] = []
    weekly_best: dict[str, tuple[float, str]] = {}
    best_row: dict[str, Any] | None = None
    best_score = -1.0
    pr_load = 0.0
    pr_reps = 0
    pr_e1rm = 0.0

    for session in ordered:
        local_best = 0.0
        for row in session["sets"]:
            weight = row.get("weight_kg")
            reps = row.get("reps")
            e1rm = estimate_e1rm(weight, reps)
            if e1rm is not None:
                pr_e1rm = max(pr_e1rm, e1rm)
                local_best = max(local_best, e1rm)
            if isinstance(weight, (int, float)):
                pr_load = max(pr_load, float(weight))
            if isinstance(reps, (int, float)):
                pr_reps = max(pr_reps, int(reps))

            score = (e1rm or 0.0) + float(weight or 0.0) * 0.01 + float(reps or 0.0) * 0.001
            if score > best_score:
                best_score = score
                best_row = row

        if local_best > 0:
            session_best_e1rm.append(local_best)
            week_key = str(session["start"].date() - timedelta(days=session["start"].weekday()))
            prev = weekly_best.get(week_key)
            if prev is None or local_best > prev[0]:
                weekly_best[week_key] = (local_best, session["workout_id"])

    trend_label, trend_change = classify_trend(session_best_e1rm)
    trend_suffix = f" ({format_number(trend_change, 1)}%)" if trend_change is not None else ""
    best_set_text = format_set(best_row) if best_row is not None else "n/a"

    summary = (
        f"{selected.get('title', query)} trend: {trend_label}{trend_suffix}. "
        f"Best set in window: {best_set_text}."
    )
    window = (
        f"Last {requested_weeks} week(s): {start.date()} to {now.date()} | "
        f"sessions: {len(ordered)} | sets: {len(filtered)}"
    )

    details = [
        f"- PR load: {format_number(pr_load)}kg" if pr_load else "- PR load: n/a",
        f"- PR reps: {pr_reps}" if pr_reps else "- PR reps: n/a",
        f"- Peak e1RM: {format_number(pr_e1rm)}kg" if pr_e1rm else "- Peak e1RM: n/a",
        "- Weekly best e1RM:",
    ]
    for week in sorted(weekly_best.keys())[-8:]:
        e1rm_val, wid = weekly_best[week]
        desc = service.get_workout_description(wid)
        suffix = f" ({desc})" if desc else ""
        details.append(f"- {week}: {format_number(e1rm_val)}kg{suffix}")

    notes = [
        "- e1RM formula: weight * (1 + reps/30).",
        "- Only working sets are included (normal, failure, dropset).",
    ]
    return render_response(summary, window, details, notes)
