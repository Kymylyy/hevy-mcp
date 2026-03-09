from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from ..errors import NoDataError
from ..response import render_response
from ..service import HevyService
from ..utils import is_working_set, utc_now
from ..validation import validate_days, validate_limit


def top_exercises(service: HevyService, days: int = 30, limit: int = 5) -> str:
    requested_days = validate_days(days)
    requested_limit = validate_limit(limit)

    now = utc_now()
    start = now - timedelta(days=requested_days)
    workouts = service.client.get_workouts_since(start)
    if not workouts:
        raise NoDataError(
            "No workouts found in the requested window.",
            "Increase days and retry.",
        )

    # Track per exercise: unique workout sessions and working set count (tiebreaker)
    sessions_by_template: dict[str, set[str]] = defaultdict(set)
    working_sets_by_template: dict[str, int] = defaultdict(int)
    title_by_template: dict[str, str] = {}

    for workout in workouts:
        workout_id = str(workout.get("id", id(workout)))
        exercises = workout.get("exercises", [])
        if not isinstance(exercises, list):
            continue
        for exercise in exercises:
            if not isinstance(exercise, dict):
                continue
            template_id = str(exercise.get("exercise_template_id", "")).strip()
            if not template_id:
                continue

            sessions_by_template[template_id].add(workout_id)

            # Capture title from workout data as fallback
            title = exercise.get("title")
            if isinstance(title, str) and title.strip():
                title_by_template[template_id] = title.strip()

            set_rows = exercise.get("sets", [])
            if isinstance(set_rows, list):
                for row in set_rows:
                    if isinstance(row, dict) and is_working_set(row.get("type")):
                        working_sets_by_template[template_id] += 1

    if not sessions_by_template:
        raise NoDataError(
            "No exercises found in workouts.",
            "Increase days and retry.",
        )

    # Override with canonical template titles
    for template in service.load_templates():
        tid = str(template.get("id", ""))
        if tid in title_by_template:
            canonical = template.get("title")
            if isinstance(canonical, str) and canonical.strip():
                title_by_template[tid] = canonical.strip()

    # Sort: session count desc, working sets desc (tiebreaker)
    ranked = sorted(
        sessions_by_template.keys(),
        key=lambda tid: (len(sessions_by_template[tid]), working_sets_by_template[tid]),
        reverse=True,
    )

    top = ranked[:requested_limit]
    details: list[str] = []
    for rank, tid in enumerate(top, 1):
        name = title_by_template.get(tid, tid)
        session_count = len(sessions_by_template[tid])
        sets_count = working_sets_by_template[tid]
        line = f"- {rank}. {name} — {session_count} session(s), {sets_count} working set(s)"
        details.append(line)

    summary = (
        f"Top {len(top)} exercise(s) by session frequency over {requested_days} day(s)."
    )
    window = f"{start.date()} to {now.date()}"
    notes = [
        "- Ranked by unique workout sessions, then working sets as tiebreaker.",
        "- Exercise names match tool_exercise_progression input.",
    ]
    return render_response(summary, window, details, notes)
