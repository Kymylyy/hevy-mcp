from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from hevy_mcp.errors import NoDataError, ValidationError
from hevy_mcp.service import HevyService
from hevy_mcp.tools import weekly_volume


class VolumeClient:
    def __init__(self, workouts: list[dict[str, Any]] | None = None) -> None:
        self.request_count = 0
        self._workouts = workouts if workouts is not None else [
            {
                "start_time": "2026-02-20T10:00:00+00:00",
                "exercises": [
                    {
                        "exercise_template_id": "SQ",
                        "sets": [
                            {"type": "normal", "weight_kg": 100, "reps": 5},
                            {"type": "normal", "weight_kg": 100, "reps": 5},
                        ],
                    },
                    {
                        "exercise_template_id": "ROW",
                        "sets": [
                            {"type": "normal", "weight_kg": 60, "reps": 10},
                        ],
                    },
                ],
            }
        ]

    def paginate(
        self,
        path: str,
        key: str,
        page_size: int,
        params: Any = None,
    ) -> list[dict[str, Any]]:
        assert path == "/exercise_templates"
        return [
            {
                "id": "SQ",
                "title": "Squat",
                "primary_muscle_group": "quadriceps",
                "secondary_muscle_groups": ["glutes", "hamstrings"],
            },
            {
                "id": "ROW",
                "title": "Row",
                "primary_muscle_group": "upper_back",
                "secondary_muscle_groups": ["lats", "biceps"],
            },
        ]

    def get_workouts_since(self, _start: datetime) -> list[dict[str, Any]]:
        return self._workouts

    def get_exercise_history(self, _template_id: str) -> list[dict[str, Any]]:
        return []

    def get_routine_folders(self) -> list[dict[str, Any]]:
        return []


def test_weekly_volume_outputs_balance_ratios() -> None:
    service = HevyService(client=VolumeClient())

    output = weekly_volume(service, weeks=4)
    assert "## Summary" in output
    assert "Push/Pull ratio" in output
    assert "Quad/Hamstring ratio" in output
    assert "Upper/Lower ratio" in output


def test_weekly_volume_raises_when_no_working_sets() -> None:
    service = HevyService(
        client=VolumeClient(
            workouts=[
                {
                    "start_time": "2026-02-20T10:00:00+00:00",
                    "exercises": [{"exercise_template_id": "SQ", "sets": [{"type": "warmup"}]}],
                }
            ]
        )
    )

    with pytest.raises(NoDataError):
        weekly_volume(service, weeks=4)


def test_weekly_volume_validates_weeks_range() -> None:
    service = HevyService(client=VolumeClient())

    with pytest.raises(ValidationError):
        weekly_volume(service, weeks=0)
