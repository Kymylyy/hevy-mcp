from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

import pytest

from hevy_mcp.errors import NoDataError, NotFoundError, ValidationError
from hevy_mcp.service import HevyService
from hevy_mcp.tools import (
    exercise_progression,
    fatigue_check,
    get_routines,
    recent_workouts,
    search_exercise,
    suggest_accessories,
    training_log,
)
from hevy_mcp.utils import utc_now


class ToolClient:
    def __init__(
        self,
        templates: list[dict[str, Any]] | None = None,
        workouts: list[dict[str, Any]] | None = None,
        history_by_template: Mapping[str, list[dict[str, Any]]] | None = None,
        routines: list[dict[str, Any]] | None = None,
        folders: list[dict[str, Any]] | None = None,
    ) -> None:
        self.templates = templates or []
        self.workouts = workouts or []
        self.history_by_template = dict(history_by_template or {})
        self.routines = routines or []
        self.folders = folders or []
        self.request_count = 0

    def paginate(
        self,
        path: str,
        key: str,
        page_size: int,
        params: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self.request_count += 1
        if path == "/exercise_templates":
            assert key == "exercise_templates"
            assert page_size == 100
            return self.templates
        if path == "/routines":
            assert key == "routines"
            return self.routines
        raise AssertionError(f"Unexpected path: {path} | params={params}")

    def get_exercise_history(self, template_id: str) -> list[dict[str, Any]]:
        self.request_count += 1
        return self.history_by_template.get(template_id, [])

    def get_workouts_since(self, _start_time: datetime) -> list[dict[str, Any]]:
        self.request_count += 1
        return self.workouts

    def get_routine_folders(self) -> list[dict[str, Any]]:
        self.request_count += 1
        return self.folders


def _iso_days_ago(days: int, minutes: int = 0) -> str:
    return (utc_now() - timedelta(days=days, minutes=minutes)).isoformat()


def test_search_exercise_not_found() -> None:
    service = HevyService(
        client=ToolClient(
            templates=[{"id": "1", "title": "Bench Press"}],
            workouts=[],
        )
    )

    with pytest.raises(NotFoundError):
        search_exercise(service, "zzzzzzzz")


def test_search_exercise_validates_name() -> None:
    service = HevyService(client=ToolClient())

    with pytest.raises(ValidationError):
        search_exercise(service, "a")


def test_exercise_progression_success() -> None:
    templates = [{"id": "T1", "title": "Bench Press"}]
    history = {
        "T1": [
            {
                "workout_id": "w1",
                "workout_title": "Push",
                "workout_start_time": _iso_days_ago(20),
                "set_type": "normal",
                "weight_kg": 90,
                "reps": 5,
            },
            {
                "workout_id": "w2",
                "workout_title": "Push",
                "workout_start_time": _iso_days_ago(13),
                "set_type": "normal",
                "weight_kg": 95,
                "reps": 5,
            },
            {
                "workout_id": "w3",
                "workout_title": "Push",
                "workout_start_time": _iso_days_ago(6),
                "set_type": "normal",
                "weight_kg": 100,
                "reps": 5,
            },
        ]
    }
    service = HevyService(client=ToolClient(templates=templates, history_by_template=history))

    output = exercise_progression(service, "bench", weeks=8)

    assert "trend:" in output
    assert "## Details" in output
    assert "Peak e1RM" in output


def test_exercise_progression_raises_no_data_when_no_working_sets() -> None:
    templates = [{"id": "T1", "title": "Bench Press"}]
    history = {
        "T1": [
            {
                "workout_id": "w1",
                "workout_title": "Push",
                "workout_start_time": _iso_days_ago(6),
                "set_type": "warmup",
                "weight_kg": 20,
                "reps": 10,
            }
        ]
    }
    service = HevyService(client=ToolClient(templates=templates, history_by_template=history))

    with pytest.raises(NoDataError):
        exercise_progression(service, "bench", weeks=8)


def test_exercise_progression_validates_weeks() -> None:
    service = HevyService(client=ToolClient())

    with pytest.raises(ValidationError):
        exercise_progression(service, "bench", weeks=0)


def test_recent_workouts_success() -> None:
    workouts = [
        {
            "title": "Upper",
            "start_time": _iso_days_ago(1, minutes=70),
            "end_time": _iso_days_ago(1),
            "exercises": [
                {
                    "title": "Bench Press",
                    "sets": [
                        {"type": "warmup", "weight_kg": 50, "reps": 8},
                        {"type": "normal", "weight_kg": 100, "reps": 5},
                        {"type": "normal", "weight_kg": 100, "reps": 5},
                        {"type": "failure", "weight_kg": 105, "reps": 5},
                    ],
                }
            ],
        }
    ]
    service = HevyService(client=ToolClient(workouts=workouts))

    output = recent_workouts(service, days=7)

    assert "Average duration" in output
    assert "Bench Press" in output
    assert "4 set(s) | warmup 1, working 3 (failure 1)" in output
    assert "1x 50kg x 8 [warmup]" in output
    assert "2x 100kg x 5" in output
    assert "1x 105kg x 5+ [failure]" in output


def test_recent_workouts_ignores_none_description_and_notes() -> None:
    workouts = [
        {
            "id": "w1",
            "title": "Upper",
            "description": None,
            "start_time": _iso_days_ago(1, minutes=70),
            "end_time": _iso_days_ago(1),
            "exercises": [
                {
                    "title": "Bench Press",
                    "notes": None,
                    "sets": [
                        {"type": "normal", "weight_kg": 100, "reps": 5},
                    ],
                }
            ],
        }
    ]
    service = HevyService(client=ToolClient(workouts=workouts))

    output = recent_workouts(service, days=7)

    assert "(None)" not in output
    assert "[None]" not in output


def test_recent_workouts_includes_exercises_beyond_sixth_entry() -> None:
    exercises = [
        {
            "title": f"Exercise {index}",
            "sets": [
                {"type": "normal", "weight_kg": index * 10, "reps": index},
            ],
        }
        for index in range(1, 8)
    ]
    workouts = [
        {
            "title": "Full Body",
            "start_time": _iso_days_ago(1, minutes=45),
            "end_time": _iso_days_ago(1),
            "exercises": exercises,
        }
    ]
    service = HevyService(client=ToolClient(workouts=workouts))

    output = recent_workouts(service, days=7)

    assert "Exercise 6" in output
    assert "Exercise 7" in output
    assert "1x 70kg x 7" in output


def test_recent_workouts_raises_when_empty() -> None:
    service = HevyService(client=ToolClient(workouts=[]))

    with pytest.raises(NoDataError):
        recent_workouts(service, days=7)


def test_recent_workouts_validates_days() -> None:
    service = HevyService(client=ToolClient())

    with pytest.raises(ValidationError):
        recent_workouts(service, days=0)


def test_fatigue_check_success() -> None:
    workouts = [
        {
            "start_time": _iso_days_ago(18),
            "exercises": [
                {"title": "Bench Press", "sets": [{"type": "normal", "weight_kg": 100, "reps": 5}]}
            ],
        },
        {
            "start_time": _iso_days_ago(14),
            "exercises": [
                {
                    "title": "Bench Press",
                    "sets": [{"type": "normal", "weight_kg": 97.5, "reps": 5}],
                }
            ],
        },
        {
            "start_time": _iso_days_ago(10),
            "exercises": [
                {
                    "title": "Bench Press",
                    "sets": [{"type": "failure", "weight_kg": 92.5, "reps": 4}],
                }
            ],
        },
        {
            "start_time": _iso_days_ago(6),
            "exercises": [
                {"title": "Bench Press", "sets": [{"type": "failure", "weight_kg": 90, "reps": 4}]}
            ],
        },
    ]
    service = HevyService(client=ToolClient(workouts=workouts))

    output = fatigue_check(service)

    assert "Fatigue risk level" in output
    assert "Triggered signals" in output


def test_fatigue_check_raises_when_empty() -> None:
    service = HevyService(client=ToolClient(workouts=[]))

    with pytest.raises(NoDataError):
        fatigue_check(service)


def test_fatigue_check_can_report_no_signals() -> None:
    workouts = [
        {
            "start_time": _iso_days_ago(16),
            "exercises": [
                {"title": "Row", "sets": [{"type": "normal", "weight_kg": 60, "reps": 10}]}
            ],
        },
        {
            "start_time": _iso_days_ago(12),
            "exercises": [
                {"title": "Row", "sets": [{"type": "normal", "weight_kg": 60, "reps": 10}]}
            ],
        },
        {
            "start_time": _iso_days_ago(8),
            "exercises": [
                {"title": "Row", "sets": [{"type": "normal", "weight_kg": 60, "reps": 10}]}
            ],
        },
        {
            "start_time": _iso_days_ago(4),
            "exercises": [
                {"title": "Row", "sets": [{"type": "normal", "weight_kg": 60, "reps": 10}]}
            ],
        },
    ]
    service = HevyService(client=ToolClient(workouts=workouts))

    output = fatigue_check(service)

    assert "Triggered signals: none" in output


def test_suggest_accessories_success() -> None:
    templates = [
        {
            "id": "t_chest",
            "title": "Chest Fly",
            "primary_muscle_group": "chest",
            "secondary_muscle_groups": ["shoulders"],
            "is_custom": False,
        },
        {
            "id": "t_back",
            "title": "Lat Pulldown",
            "primary_muscle_group": "lats",
            "secondary_muscle_groups": ["biceps"],
            "is_custom": False,
        },
    ]
    workouts = [
        {
            "start_time": _iso_days_ago(3),
            "exercises": [
                {
                    "exercise_template_id": "t_chest",
                    "sets": [{"type": "normal", "weight_kg": 30, "reps": 12}],
                }
            ],
        }
    ]
    service = HevyService(client=ToolClient(templates=templates, workouts=workouts))

    output = suggest_accessories(service)

    assert "Accessory priorities" in output
    assert "Lat Pulldown" in output


def test_suggest_accessories_raises_when_no_workouts() -> None:
    service = HevyService(
        client=ToolClient(
            templates=[{"id": "x", "title": "Curl", "primary_muscle_group": "biceps"}]
        )
    )

    with pytest.raises(NoDataError):
        suggest_accessories(service)


def test_suggest_accessories_raises_when_no_candidates() -> None:
    workouts = [{"start_time": _iso_days_ago(1), "exercises": []}]
    service = HevyService(client=ToolClient(templates=[], workouts=workouts))

    with pytest.raises(NoDataError):
        suggest_accessories(service)


def test_training_log_success() -> None:
    workouts = [
        {"start_time": _iso_days_ago(5), "title": "Upper A", "exercises": []},
        {"start_time": _iso_days_ago(2), "title": "Lower B", "exercises": []},
    ]
    service = HevyService(client=ToolClient(workouts=workouts))

    output = training_log(service, days=30)

    assert "sessions/week" in output
    assert "Average gap" in output


def test_training_log_raises_when_empty() -> None:
    service = HevyService(client=ToolClient(workouts=[]))

    with pytest.raises(NoDataError):
        training_log(service, days=30)


def test_training_log_validates_days() -> None:
    service = HevyService(client=ToolClient())

    with pytest.raises(ValidationError):
        training_log(service, days=366)


def test_get_routines_raises_when_empty() -> None:
    service = HevyService(client=ToolClient(routines=[]))

    with pytest.raises(NoDataError):
        get_routines(service)


def test_get_routines_truncates_exercise_rows() -> None:
    exercises = [{"title": f"Exercise {index}", "sets_count": 1} for index in range(15)]
    routines = [{"id": "r1", "title": "Long Routine", "exercises": exercises}]
    service = HevyService(client=ToolClient(routines=routines, folders=[]))

    output = get_routines(service)

    assert "... 3 more exercise(s)" in output
    assert "Unfiled" in output
