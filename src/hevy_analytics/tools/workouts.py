from __future__ import annotations

from datetime import timedelta
from statistics import mean
from typing import Any

from ..config import DEFAULT_RECENT_WORKOUTS_LIMIT
from ..errors import NoDataError
from ..response import ToolResult, build_result
from ..service import HevyService
from ..utils import (
    format_number,
    is_working_set,
    parse_iso_datetime,
    utc_now,
)
from ..validation import validate_days, validate_limit
from ._shared import summarize_set_scheme


def recent_workouts(
    service: HevyService,
    days: int = 7,
    limit: int = DEFAULT_RECENT_WORKOUTS_LIMIT,
) -> ToolResult:
    requested_days = validate_days(days)
    requested_limit = validate_limit(limit)
    now = utc_now()
    start = now - timedelta(days=requested_days)
    workouts = service.client.get_workouts_since(start)
    service.cache_workout_descriptions_since(start, workouts)
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
    data_workouts: list[dict[str, Any]] = []

    for workout in ordered[:requested_limit]:
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

        raw_description = workout.get("description", "")
        description = raw_description.strip() if isinstance(raw_description, str) else ""
        summaries: list[str] = []
        data_exercises: list[dict[str, Any]] = []
        for exercise in workout.get("exercises", []):
            if not isinstance(exercise, dict):
                continue
            title = str(exercise.get("title", "Exercise"))
            sets = exercise.get("sets", [])
            if not isinstance(sets, list):
                continue
            set_rows = [row for row in sets if isinstance(row, dict)]
            if not set_rows:
                continue
            warmup_count = 0
            working_count = 0
            failure_count = 0
            for row in set_rows:
                set_type = row.get("type")
                if set_type == "warmup":
                    warmup_count += 1
                elif is_working_set(set_type):
                    working_count += 1
                    if set_type == "failure":
                        failure_count += 1
            counts = f"{len(set_rows)} set(s) | warmup {warmup_count}, working {working_count}"
            if failure_count:
                counts += f" (failure {failure_count})"
            set_text = f"{title}: {counts} | {summarize_set_scheme(set_rows)}"
            raw_notes = exercise.get("notes", "")
            exercise_notes = raw_notes.strip() if isinstance(raw_notes, str) else ""
            if exercise_notes:
                set_text += f" [{exercise_notes}]"
            summaries.append(set_text)
            data_exercises.append(
                {
                    "title": title,
                    "notes": exercise_notes or None,
                    "set_count": len(set_rows),
                    "warmup_count": warmup_count,
                    "working_count": working_count,
                    "failure_count": failure_count,
                    "set_scheme": summarize_set_scheme(set_rows),
                }
            )

        if not summaries:
            summaries.append("no sets logged")

        workout_label = workout.get("title", "Workout")
        if description:
            workout_label = f"{workout_label} ({description})"
        details.append(
            f"- {start_at.date()} | {workout_label} | "
            f"{format_number(duration_minutes)} min | {'; '.join(summaries)}"
        )
        data_workouts.append(
            {
                "id": str(workout.get("id", "")) or None,
                "title": str(workout.get("title", "Workout")),
                "description": description or None,
                "start_time": start_raw,
                "end_time": end_raw if isinstance(end_raw, str) else None,
                "date": str(start_at.date()),
                "duration_minutes": duration_minutes,
                "exercises": data_exercises,
            }
        )

    avg_duration = mean(durations) if durations else 0.0
    summary = (
        f"{len(ordered)} workout(s) in last {requested_days} day(s). "
        f"Average duration: {format_number(avg_duration)} minutes."
    )
    notes = [
        "- All logged sets are included in summaries.",
        "- Working sets include: normal, failure, dropset (failure is counted as working).",
    ]
    if len(ordered) > requested_limit:
        notes.append(f"- Output truncated to {requested_limit} workouts.")
    data = {
        "window": {
            "days": requested_days,
            "start_date": str(start.date()),
            "end_date": str(now.date()),
        },
        "total_workouts": len(ordered),
        "returned_workouts": len(data_workouts),
        "average_duration_minutes": avg_duration,
        "truncated": len(ordered) > requested_limit,
        "workouts": data_workouts,
    }
    return build_result(summary, f"{start.date()} to {now.date()}", details, notes, data=data)
