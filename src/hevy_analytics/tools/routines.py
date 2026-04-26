from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..config import MAX_ROUTINE_EXERCISES_OUTPUT
from ..errors import NoDataError
from ..response import ToolResult, build_result
from ..service import HevyService
from ._shared import summarize_set_scheme


def get_routines(service: HevyService) -> ToolResult:
    routines = service.client.paginate("/routines", "routines", page_size=10)
    folders = service.client.get_routine_folders()
    if not routines:
        raise NoDataError(
            "No routines returned by Hevy API.",
            "Create at least one routine in Hevy and retry.",
        )

    folder_names = {
        str(folder.get("id")): str(folder.get("title", folder.get("name", "Unnamed Folder")))
        for folder in folders
        if isinstance(folder, dict)
    }

    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for routine in routines:
        folder_id = routine.get("routine_folder_id", routine.get("folder_id"))
        grouped[folder_names.get(str(folder_id), "Unfiled")].append(routine)

    details: list[str] = []
    folder_data: list[dict[str, Any]] = []
    for folder_name in sorted(grouped.keys()):
        details.append(f"- {folder_name}:")
        routines_data: list[dict[str, Any]] = []
        for routine in sorted(grouped[folder_name], key=lambda row: str(row.get("title", ""))):
            title = str(routine.get("title", "Untitled Routine"))
            exercises = routine.get("exercises", [])
            total_exercises = 0
            exercise_lines: list[str] = []
            planned_sets = 0
            structured_exercises: list[dict[str, Any]] = []
            if isinstance(exercises, list):
                shown = 0
                for exercise in exercises:
                    if not isinstance(exercise, dict):
                        continue
                    total_exercises += 1
                    exercise_title = str(exercise.get("title", "Exercise"))
                    set_rows = exercise.get("sets")
                    sets_count = exercise.get("sets_count")
                    set_plan = "no set plan"

                    if isinstance(set_rows, list):
                        structured_sets = sum(1 for row in set_rows if isinstance(row, dict))
                        if structured_sets > 0:
                            planned_sets += structured_sets
                            set_plan = summarize_set_scheme(set_rows)
                        elif isinstance(sets_count, int):
                            planned_sets += sets_count
                            set_plan = f"{sets_count} set(s) planned"
                    elif isinstance(sets_count, int):
                        planned_sets += sets_count
                        set_plan = f"{sets_count} set(s) planned"
                    structured_exercises.append(
                        {
                            "title": exercise_title,
                            "set_plan": set_plan,
                        }
                    )
                    if shown < MAX_ROUTINE_EXERCISES_OUTPUT:
                        exercise_lines.append(f"  - {exercise_title}: {set_plan}")
                        shown += 1

                hidden = max(total_exercises - MAX_ROUTINE_EXERCISES_OUTPUT, 0)
                if hidden:
                    exercise_lines.append(f"  - ... {hidden} more exercise(s)")

            details.append(
                f"- {title} ({total_exercises} exercise(s), {planned_sets} planned sets)"
            )
            if exercise_lines:
                details.extend(exercise_lines)
            else:
                details.append("  - no exercises")
            routines_data.append(
                {
                    "id": str(routine.get("id", "")) or None,
                    "title": title,
                    "total_exercises": total_exercises,
                    "planned_sets": planned_sets,
                    "exercises": structured_exercises,
                }
            )
        folder_data.append({"name": folder_name, "routines": routines_data})

    summary = f"{len(routines)} routine(s) across {max(len(folder_names), 1)} folder(s)."
    notes = ["- Routines without folder mapping are listed under Unfiled."]
    data = {
        "routine_count": len(routines),
        "folder_count": max(len(folder_names), 1),
        "folders": folder_data,
    }
    return build_result(summary, "Current routine catalog", details, notes, data=data)
