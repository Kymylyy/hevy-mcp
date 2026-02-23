from typing import Any

from hevy_mcp.service import HevyService


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


def test_rank_templates_prefers_exact_then_contains_then_fuzzy() -> None:
    client = StubClient(
        [
            {"id": "1", "title": "Squat (Barbell)"},
            {"id": "2", "title": "Front Squat"},
            {"id": "3", "title": "Bulgarian Split Squat"},
            {"id": "4", "title": "Bench Press"},
        ]
    )
    service = HevyService(client=client)  # type: ignore[arg-type]

    matches = service.rank_templates("squat (barbell)")
    assert matches[0]["title"] == "Squat (Barbell)"

    contains_matches = service.rank_templates("front")
    assert contains_matches[0]["title"] == "Front Squat"


def test_rank_templates_uses_cache_on_repeated_query() -> None:
    client = StubClient([{"id": "1", "title": "Shoulder Press"}])
    service = HevyService(client=client)  # type: ignore[arg-type]

    first = service.rank_templates("shoulder")
    second = service.rank_templates("shoulder")

    assert first == second
    assert client.request_count == 1
