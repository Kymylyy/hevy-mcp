from __future__ import annotations

from datetime import datetime
from typing import Any

from hevy_analytics.service import HevyService


class StubClient:
    def __init__(self, templates: list[dict[str, Any]]) -> None:
        self.templates = templates
        self.request_count = 0

    def paginate(
        self,
        path: str,
        key: str,
        page_size: int,
        params: Any = None,
    ) -> list[dict[str, Any]]:
        assert path == "/exercise_templates"
        assert key == "exercise_templates"
        assert page_size == 100
        self.request_count += 1
        return self.templates

    def get_exercise_history(self, _template_id: str) -> list[dict[str, Any]]:
        return []

    def get_workouts_since(self, _start_time: datetime) -> list[dict[str, Any]]:
        return []

    def get_routine_folders(self) -> list[dict[str, Any]]:
        return []


def test_rank_templates_prefers_exact_then_contains_then_fuzzy() -> None:
    client = StubClient(
        [
            {"id": "1", "title": "Squat (Barbell)"},
            {"id": "2", "title": "Front Squat"},
            {"id": "3", "title": "Bulgarian Split Squat"},
            {"id": "4", "title": "Bench Press"},
        ]
    )
    service = HevyService(client=client)

    matches = service.rank_templates("squat (barbell)")
    assert matches[0]["title"] == "Squat (Barbell)"

    contains_matches = service.rank_templates("front")
    assert contains_matches[0]["title"] == "Front Squat"


def test_rank_templates_uses_cache_on_repeated_query() -> None:
    client = StubClient([{"id": "1", "title": "Shoulder Press"}])
    service = HevyService(client=client)

    first = service.rank_templates("shoulder")
    second = service.rank_templates("shoulder")

    assert first == second
    assert client.request_count == 1


def test_load_workout_descriptions_since_extends_cache_window() -> None:
    now = datetime.fromisoformat("2026-03-04T12:00:00+00:00")

    class WindowedClient:
        def __init__(self) -> None:
            self.request_count = 0

        def paginate(
            self,
            path: str,
            key: str,
            page_size: int,
            params: Any = None,
        ) -> list[dict[str, Any]]:
            return []

        def get_exercise_history(self, _template_id: str) -> list[dict[str, Any]]:
            return []

        def get_workouts_since(self, start_time: datetime) -> list[dict[str, Any]]:
            self.request_count += 1
            if start_time >= datetime.fromisoformat("2026-02-25T12:00:00+00:00"):
                return [{"id": "new", "description": "New Gym"}]
            return [
                {"id": "new", "description": "New Gym"},
                {"id": "old", "description": "Old Gym"},
            ]

        def get_routine_folders(self) -> list[dict[str, Any]]:
            return []

    service = HevyService(client=WindowedClient())

    service.load_workout_descriptions_since(datetime.fromisoformat("2026-02-25T12:00:00+00:00"))
    assert service.get_workout_description("old") == ""

    service.load_workout_descriptions_since(now)
    assert service.get_workout_description("old") == ""

    service.load_workout_descriptions_since(datetime.fromisoformat("2025-12-10T12:00:00+00:00"))
    assert service.get_workout_description("old") == "Old Gym"
