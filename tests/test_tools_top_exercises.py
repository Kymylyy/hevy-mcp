from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

import pytest

from hevy_mcp.errors import NoDataError, ValidationError
from hevy_mcp.service import HevyService
from hevy_mcp.tools import top_exercises
from hevy_mcp.utils import utc_now


class TopExercisesClient:
    def __init__(
        self,
        templates: list[dict[str, Any]] | None = None,
        workouts: list[dict[str, Any]] | None = None,
    ) -> None:
        self.templates = templates or []
        self.workouts = workouts or []
        self.request_count = 0

    def paginate(
        self,
        path: str,
        key: str,
        page_size: int,
        params: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self.request_count += 1
        return self.templates

    def get_exercise_history(self, template_id: str) -> list[dict[str, Any]]:
        self.request_count += 1
        return []

    def get_workouts_since(self, _start_time: datetime) -> list[dict[str, Any]]:
        self.request_count += 1
        return self.workouts

    def get_routine_folders(self) -> list[dict[str, Any]]:
        self.request_count += 1
        return []


def _make_workout(
    workout_id: str,
    exercises: list[dict[str, Any]],
    days_ago: int = 1,
) -> dict[str, Any]:
    from datetime import timedelta

    start = utc_now() - timedelta(days=days_ago)
    return {
        "id": workout_id,
        "start_time": start.isoformat(),
        "exercises": exercises,
    }


def _make_exercise(
    template_id: str,
    title: str,
    working_sets: int = 1,
    warmup_sets: int = 0,
) -> dict[str, Any]:
    sets: list[dict[str, Any]] = []
    for _ in range(warmup_sets):
        sets.append({"type": "warmup", "weight_kg": 20, "reps": 10})
    for _ in range(working_sets):
        sets.append({"type": "normal", "weight_kg": 100, "reps": 5})
    return {
        "exercise_template_id": template_id,
        "title": title,
        "sets": sets,
    }


def test_ranks_by_session_frequency() -> None:
    """Exercise in 3 workouts beats exercise in 1 workout with 10 sets."""
    workouts = [
        _make_workout("w1", [_make_exercise("SQ", "Squat", working_sets=1)], days_ago=5),
        _make_workout("w2", [_make_exercise("SQ", "Squat", working_sets=1)], days_ago=3),
        _make_workout("w3", [_make_exercise("SQ", "Squat", working_sets=1)], days_ago=1),
        _make_workout("w4", [_make_exercise("BP", "Bench Press", working_sets=10)], days_ago=2),
    ]
    service = HevyService(client=TopExercisesClient(workouts=workouts))

    output = top_exercises(service, days=30, limit=5)

    squat_pos = output.index("Squat")
    bench_pos = output.index("Bench Press")
    assert squat_pos < bench_pos


def test_limit_restricts_output() -> None:
    """5 exercises available, limit=2 → only 2 shown."""
    workouts = [
        _make_workout("w1", [
            _make_exercise("A", "ExA"),
            _make_exercise("B", "ExB"),
            _make_exercise("C", "ExC"),
            _make_exercise("D", "ExD"),
            _make_exercise("E", "ExE"),
        ]),
    ]
    service = HevyService(client=TopExercisesClient(workouts=workouts))

    output = top_exercises(service, days=30, limit=2)

    assert "Top 2 exercise(s)" in output
    # Only 2 entries in details
    detail_lines = [
        line for line in output.split("\n")
        if line.startswith("- ") and "session(s)" in line
    ]
    assert len(detail_lines) == 2


def test_uses_canonical_template_titles() -> None:
    """Resolves template_id to template title from load_templates."""
    templates = [{"id": "SQ", "title": "Barbell Squat (Canonical)"}]
    workouts = [
        _make_workout("w1", [_make_exercise("SQ", "Squat (workout title)")]),
    ]
    service = HevyService(client=TopExercisesClient(templates=templates, workouts=workouts))

    output = top_exercises(service, days=30, limit=5)

    assert "Barbell Squat (Canonical)" in output
    assert "Squat (workout title)" not in output


def test_tiebreaker_by_working_sets() -> None:
    """Equal sessions → more working sets wins."""
    workouts = [
        _make_workout("w1", [
            _make_exercise("A", "ExA", working_sets=5),
            _make_exercise("B", "ExB", working_sets=1),
        ]),
    ]
    service = HevyService(client=TopExercisesClient(workouts=workouts))

    output = top_exercises(service, days=30, limit=5)

    a_pos = output.index("ExA")
    b_pos = output.index("ExB")
    assert a_pos < b_pos


def test_raises_no_data_on_empty_workouts() -> None:
    service = HevyService(client=TopExercisesClient(workouts=[]))

    with pytest.raises(NoDataError):
        top_exercises(service, days=30, limit=5)


def test_validates_days() -> None:
    service = HevyService(client=TopExercisesClient())

    with pytest.raises(ValidationError):
        top_exercises(service, days=0, limit=5)


def test_validates_limit() -> None:
    service = HevyService(client=TopExercisesClient())

    with pytest.raises(ValidationError):
        top_exercises(service, days=30, limit=0)
