from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

from ..errors import NoDataError
from ..response import render_response
from ..service import HevyService
from ..utils import is_working_set, parse_iso_datetime, utc_now


def suggest_accessories(service: HevyService) -> str:
    now = utc_now()
    baseline_start = now - timedelta(weeks=4)
    recent_start = now - timedelta(days=10)
    very_recent_start = now - timedelta(days=2)
    workouts = service.client.get_workouts_since(baseline_start)
    if not workouts:
        raise NoDataError(
            "No workouts available for accessory recommendations.",
            "Log sessions first, then rerun suggest_accessories.",
        )

    templates = service.load_templates()
    templates_by_id = {str(row.get("id")): row for row in templates}
    by_primary: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for template in templates:
        primary = template.get("primary_muscle_group")
        if isinstance(primary, str):
            by_primary[primary].append(template)

    recent: defaultdict[str, float] = defaultdict(float)
    baseline: defaultdict[str, float] = defaultdict(float)
    very_recent: defaultdict[str, float] = defaultdict(float)

    for workout in workouts:
        start_raw = workout.get("start_time")
        if not isinstance(start_raw, str):
            continue
        workout_time = parse_iso_datetime(start_raw)
        for exercise in workout.get("exercises", []):
            if not isinstance(exercise, dict):
                continue
            template = templates_by_id.get(str(exercise.get("exercise_template_id", "")), {})
            primary = str(template.get("primary_muscle_group", "other"))
            secondaries = [
                item
                for item in template.get("secondary_muscle_groups", [])
                if isinstance(item, str)
            ]

            sets = exercise.get("sets", [])
            if not isinstance(sets, list):
                continue
            for set_row in sets:
                if not isinstance(set_row, dict) or not is_working_set(set_row.get("type")):
                    continue
                baseline[primary] += 1.0
                for muscle in secondaries:
                    baseline[muscle] += 0.5
                if workout_time >= recent_start:
                    recent[primary] += 1.0
                    for muscle in secondaries:
                        recent[muscle] += 0.5
                if workout_time >= very_recent_start:
                    very_recent[primary] += 1.0
                    for muscle in secondaries:
                        very_recent[muscle] += 0.5

    muscles = sorted(
        {
            str(row.get("primary_muscle_group", "other"))
            for row in templates
            if isinstance(row.get("primary_muscle_group"), str)
        }
    )
    chronic = [muscle for muscle in muscles if baseline[muscle] / 4.0 < 4.0]
    recent_under = [muscle for muscle in muscles if recent[muscle] < 3.0]
    heavily = {muscle for muscle, value in very_recent.items() if value >= 4.0}

    priority: list[str] = []
    for muscle in sorted(chronic, key=lambda row: baseline[row]):
        if muscle not in priority:
            priority.append(muscle)
    for muscle in sorted(recent_under, key=lambda row: recent[row]):
        if muscle not in priority:
            priority.append(muscle)

    suggestions: list[tuple[str, str]] = []
    used: set[str] = set()
    for muscle in priority:
        if muscle in heavily:
            continue
        options = sorted(
            by_primary.get(muscle, []),
            key=lambda row: (bool(row.get("is_custom", False)), str(row.get("title", ""))),
        )
        for option in options:
            option_id = str(option.get("id", ""))
            title = str(option.get("title", ""))
            if not option_id or not title or option_id in used:
                continue
            suggestions.append((title, muscle))
            used.add(option_id)
            break
        if len(suggestions) >= 6:
            break

    if not suggestions:
        raise NoDataError(
            "Could not generate accessory suggestions from current data.",
            "Retry after logging more workouts with exercise-template IDs.",
        )

    summary = f"Accessory priorities: {', '.join(m for _, m in suggestions[:4])}."
    details = [
        f"- {title} ({muscle}) -> 2-4 sets, 8-20 reps, RPE 6-8"
        for title, muscle in suggestions
    ]
    notes = [
        "- Suggestions prioritize undertrained muscles and avoid heavily hit muscles in last 48h.",
        "- Keep accessory work low-fatigue and technique-focused.",
    ]
    return render_response(summary, f"Last 4 weeks up to {now.date()}", details, notes)
