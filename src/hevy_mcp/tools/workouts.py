from __future__ import annotations

from datetime import timedelta
from statistics import mean

from ..config import MAX_WORKOUT_ROWS_OUTPUT
from ..errors import NoDataError
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
from ..validation import validate_days


def recent_workouts(service: HevyService, days: int = 7) -> str:
    requested_days = validate_days(days)
    now = utc_now()
    start = now - timedelta(days=requested_days)
    workouts = service.client.get_workouts_since(start)
    service.cache_workout_descriptions(workouts)
    if not workouts:
        raise NoDataError(
            "No workouts found in the requested window.",
            "Increase days and run recent_workouts again.",
        )

    ordered = sorted(
        workouts,
        key=lambda row: parse_iso_datetime(str(row.get("start_time"))),
        reverse=True,
    )
    durations: list[float] = []
    details: list[str] = []

    for workout in ordered[:MAX_WORKOUT_ROWS_OUTPUT]:
        start_raw = workout.get("start_time")
        if not isinstance(start_raw, str):
            continue
        start_at = parse_iso_datetime(start_raw)
        end_raw = workout.get("end_time")
        duration_minutes = 0.0
        if isinstance(end_raw, str):
            duration_minutes = max(
                (parse_iso_datetime(end_raw) - start_at).total_seconds() / 60,
                0.0,
            )
            durations.append(duration_minutes)

        description = str(workout.get("description", "")).strip()
        summaries: list[str] = []
        for exercise in workout.get("exercises", []):
            if not isinstance(exercise, dict):
                continue
            title = str(exercise.get("title", "Exercise"))
            sets = exercise.get("sets", [])
            if not isinstance(sets, list):
                continue
            candidates = [
                row
                for row in sets
                if isinstance(row, dict) and is_working_set(row.get("type"))
            ]
            ranked = sorted(
                candidates,
                key=lambda row: (
                    estimate_e1rm(row.get("weight_kg"), row.get("reps")) or 0.0,
                    float(row.get("weight_kg") or 0.0),
                    float(row.get("reps") or 0.0),
                ),
                reverse=True,
            )
            if ranked:
                exercise_notes = str(exercise.get("notes", "")).strip()
                set_text = f"{title}: {', '.join(format_set(row) for row in ranked[:2])}"
                if exercise_notes:
                    set_text += f" [{exercise_notes}]"
                summaries.append(set_text)

        if not summaries:
            summaries.append("no working sets logged")

        workout_label = workout.get("title", "Workout")
        if description:
            workout_label = f"{workout_label} ({description})"
        details.append(
            f"- {start_at.date()} | {workout_label} | "
            f"{format_number(duration_minutes)} min | {'; '.join(summaries[:6])}"
        )

    avg_duration = mean(durations) if durations else 0.0
    summary = (
        f"{len(ordered)} workout(s) in last {requested_days} day(s). "
        f"Average duration: {format_number(avg_duration)} minutes."
    )
    notes = ["- Warmup sets are excluded from key-set summaries."]
    if len(ordered) > MAX_WORKOUT_ROWS_OUTPUT:
        notes.append(f"- Output truncated to {MAX_WORKOUT_ROWS_OUTPUT} workouts.")
    return render_response(summary, f"{start.date()} to {now.date()}", details, notes)
