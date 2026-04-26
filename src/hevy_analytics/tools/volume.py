from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

from ..errors import NoDataError
from ..response import ToolResult, build_result
from ..service import HevyService
from ..utils import format_number, is_working_set, parse_iso_datetime, utc_now
from ..validation import validate_weeks


def weekly_volume(service: HevyService, weeks: int = 4) -> ToolResult:
    requested_weeks = validate_weeks(weeks)
    now = utc_now()
    start = now - timedelta(weeks=requested_weeks)
    workouts = service.client.get_workouts_since(start)
    if not workouts:
        raise NoDataError(
            "No workouts available in the requested period.",
            "Increase weeks and run weekly_volume again.",
        )

    templates = {str(row.get("id")): row for row in service.load_templates()}
    weekly_credits: dict[str, defaultdict[str, float]] = defaultdict(lambda: defaultdict(float))
    muscle_totals: defaultdict[str, float] = defaultdict(float)
    working_set_count = 0

    for workout in workouts:
        start_raw = workout.get("start_time")
        if not isinstance(start_raw, str):
            continue
        workout_time = parse_iso_datetime(start_raw)
        week_key = str(workout_time.date() - timedelta(days=workout_time.weekday()))

        for exercise in workout.get("exercises", []):
            if not isinstance(exercise, dict):
                continue
            template = templates.get(str(exercise.get("exercise_template_id", "")), {})
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
                working_set_count += 1
                weekly_credits[week_key][primary] += 1.0
                muscle_totals[primary] += 1.0
                for muscle in secondaries:
                    weekly_credits[week_key][muscle] += 0.5
                    muscle_totals[muscle] += 0.5

    if working_set_count == 0:
        raise NoDataError(
            "No working sets found for volume analysis.",
            "Ensure workouts contain normal/failure/dropset entries.",
        )

    push = sum(muscle_totals[m] for m in ("chest", "shoulders", "triceps"))
    pull = sum(muscle_totals[m] for m in ("lats", "upper_back", "traps", "biceps", "forearms"))
    quads = muscle_totals["quadriceps"]
    hamstrings = muscle_totals["hamstrings"] + muscle_totals["glutes"]
    upper = sum(
        muscle_totals[m]
        for m in (
            "chest",
            "shoulders",
            "triceps",
            "lats",
            "upper_back",
            "traps",
            "biceps",
            "forearms",
        )
    )
    lower = sum(
        muscle_totals[m]
        for m in ("quadriceps", "hamstrings", "glutes", "calves", "abductors", "adductors")
    )

    def ratio(left: float, right: float) -> str:
        return "n/a" if right == 0 else format_number(left / right, 2)

    weekly_avg = sum(muscle_totals.values()) / max(requested_weeks, 1)
    sorted_muscles = sorted(muscle_totals.items(), key=lambda row: row[1], reverse=True)
    concentration = "n/a"
    if sorted_muscles:
        concentration = f"{sorted_muscles[0][0]} ({format_number(sorted_muscles[0][1])} credits)"

    details: list[str] = []
    for week in sorted(weekly_credits.keys()):
        top = sorted(weekly_credits[week].items(), key=lambda row: row[1], reverse=True)[:8]
        details.append(f"- {week}: {', '.join(f'{m}:{format_number(v)}' for m, v in top)}")
    details.extend(
        [
            f"- Push/Pull ratio: {ratio(push, pull)}",
            f"- Quad/Hamstring ratio: {ratio(quads, hamstrings)}",
            f"- Upper/Lower ratio: {ratio(upper, lower)}",
        ]
    )

    summary = (
        f"Average weekly volume: {format_number(weekly_avg)} muscle credits. "
        f"Biggest concentration: {concentration}."
    )
    notes = [
        "- Volume unit is working-set credit (primary 1.0, each secondary 0.5).",
        "- This is distribution-focused volume, not tonnage.",
    ]
    data: dict[str, Any] = {
        "window": {
            "weeks": requested_weeks,
            "start_date": str(start.date()),
            "end_date": str(now.date()),
        },
        "working_set_count": working_set_count,
        "weekly_average_credits": weekly_avg,
        "largest_concentration": {
            "muscle": sorted_muscles[0][0] if sorted_muscles else None,
            "credits": sorted_muscles[0][1] if sorted_muscles else None,
        },
        "ratios": {
            "push_pull": None if pull == 0 else push / pull,
            "quad_hamstring": None if hamstrings == 0 else quads / hamstrings,
            "upper_lower": None if lower == 0 else upper / lower,
        },
        "muscle_totals": [
            {"muscle": muscle, "credits": credits}
            for muscle, credits in sorted_muscles
        ],
        "weekly_credits": [
            {
                "week_start": week,
                "muscles": [
                    {"muscle": muscle, "credits": credits}
                    for muscle, credits in sorted(
                        weekly_credits[week].items(),
                        key=lambda row: row[1],
                        reverse=True,
                    )
                ],
            }
            for week in sorted(weekly_credits.keys())
        ],
    }
    return build_result(summary, f"{start.date()} to {now.date()}", details, notes, data=data)
