from typing import Any

from hevy_mcp.service import HevyService
from hevy_mcp.tools import weekly_volume


class VolumeClient:
    def __init__(self) -> None:
        self.request_count = 0

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

    def get_workouts_since(self, _start: Any) -> list[dict[str, Any]]:
        return [
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


def test_weekly_volume_outputs_balance_ratios() -> None:
    service = HevyService(client=VolumeClient())  # type: ignore[arg-type]

    output = weekly_volume(service, weeks=4)
    assert "## Summary" in output
    assert "Push/Pull ratio" in output
    assert "Quad/Hamstring ratio" in output
    assert "Upper/Lower ratio" in output
