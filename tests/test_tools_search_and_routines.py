from __future__ import annotations

from datetime import datetime
from typing import Any

from hevy_mcp.service import HevyService
from hevy_mcp.tools import get_routines, search_exercise


class SearchAndRoutineClient:
    def __init__(
        self,
        templates: list[dict[str, Any]],
        workouts: list[dict[str, Any]],
        routines: list[dict[str, Any]],
    ) -> None:
        self.templates = templates
        self.workouts = workouts
        self.routines = routines
        self.request_count = 0

    def paginate(
        self,
        path: str,
        key: str,
        page_size: int,
        params: Any = None,
    ) -> list[dict[str, Any]]:
        self.request_count += 1
        if path == "/exercise_templates":
            assert key == "exercise_templates"
            assert page_size == 100
            return self.templates
        if path == "/routines":
            assert key == "routines"
            return self.routines
        raise AssertionError(f"Unexpected path: {path}")

    def get_workouts_since(self, _start: datetime) -> list[dict[str, Any]]:
        return self.workouts

    def get_exercise_history(self, _template_id: str) -> list[dict[str, Any]]:
        return []

    def get_routine_folders(self) -> list[dict[str, Any]]:
        return [{"id": "folder-1", "title": "Strength"}]


def test_search_exercise_boosts_templates_from_recent_history() -> None:
    client = SearchAndRoutineClient(
        templates=[
            {"id": "row", "title": "Squat Row", "type": "weighted_bodyweight"},
            {"id": "front", "title": "Front Squat", "type": "barbell"},
            {"id": "bb", "title": "Squat (Barbell)", "type": "barbell"},
        ],
        workouts=[
            {
                "start_time": "2026-02-20T10:00:00+00:00",
                "exercises": [
                    {
                        "exercise_template_id": "bb",
                        "sets": [
                            {"type": "normal", "weight_kg": 100, "reps": 5},
                            {"type": "normal", "weight_kg": 100, "reps": 5},
                        ],
                    },
                    {
                        "exercise_template_id": "front",
                        "sets": [{"type": "normal", "weight_kg": 90, "reps": 6}],
                    },
                ],
            }
        ],
        routines=[],
    )
    service = HevyService(client=client)

    output = search_exercise(service, "squat")

    assert output.find("Squat (Barbell)") < output.find("Squat Row")
    assert "recent user history boost" in output


def test_get_routines_includes_set_schemes_per_exercise() -> None:
    client = SearchAndRoutineClient(
        templates=[],
        workouts=[],
        routines=[
            {
                "id": "r1",
                "title": "Push Day",
                "routine_folder_id": "folder-1",
                "exercises": [
                    {
                        "title": "Bench Press",
                        "sets": [
                            {
                                "type": "normal",
                                "weight_kg": 100,
                                "reps": 5,
                                "rest_seconds": 180,
                                "rir": 2,
                            },
                            {
                                "type": "normal",
                                "weight_kg": 100,
                                "reps": 5,
                                "rest_seconds": 180,
                                "rir": 2,
                            },
                            {"type": "failure", "weight_kg": 105, "reps": 5},
                        ],
                    },
                    {
                        "title": "Incline DB Press",
                        "sets_count": 3,
                    },
                ],
            }
        ],
    )
    service = HevyService(client=client)

    output = get_routines(service)

    assert "Push Day (2 exercise(s), 6 planned sets)" in output
    assert "Bench Press: 2x 100kg x 5 (RIR 2, rest 180s), 1x 105kg x 5+ [failure]" in output
    assert "Incline DB Press: 3 set(s) planned" in output
