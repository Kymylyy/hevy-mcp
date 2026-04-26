from __future__ import annotations

import json

from hevy_analytics.cli import main
from hevy_analytics.errors import NoDataError
from hevy_analytics.response import attach_meta, build_error_result, build_result
from hevy_analytics.service import HevyService


class CliClient:
    def __init__(self) -> None:
        self.request_count = 0
        self.closed = False

    def paginate(self, path, key, page_size, params=None):
        self.request_count += 1
        if path == "/exercise_templates":
            return [{"id": "bench", "title": "Bench Press"}]
        return []

    def get_exercise_history(self, template_id):
        self.request_count += 1
        return []

    def get_workouts_since(self, start_time):
        self.request_count += 1
        return []

    def get_routine_folders(self):
        self.request_count += 1
        return []

    def close(self) -> None:
        self.closed = True


def test_cli_outputs_json(monkeypatch, capsys) -> None:
    client = CliClient()
    service = HevyService(client=client)
    monkeypatch.setattr("hevy_analytics.cli.build_service", lambda: service)
    monkeypatch.setattr(
        "hevy_analytics.cli.search_exercise",
        lambda _service, name: build_result(
            f"Found 1 match(es) for '{name}'.",
            "Exercise catalog snapshot (cached up to 12h).",
            ["- Bench Press"],
            ["- note"],
            data={"query": name, "matches": [{"id": "bench", "title": "Bench Press"}]},
        ),
    )

    exit_code = main(["search-exercise", "--name", "bench"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["data"]["query"] == "bench"
    assert client.closed is True


def test_cli_outputs_markdown(monkeypatch, capsys) -> None:
    service = HevyService(client=CliClient())
    monkeypatch.setattr("hevy_analytics.cli.build_service", lambda: service)
    monkeypatch.setattr(
        "hevy_analytics.cli.fatigue_check",
        lambda _service: build_result(
            "Fatigue risk level: low.",
            "2026-01-01 to 2026-01-21",
            ["- Triggered signals: none"],
            ["- Current fatigue signal looks manageable."],
            data={"risk": "low", "signals": []},
        ),
    )

    exit_code = main(["fatigue-check", "--output", "markdown"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "## Summary" in captured.out
    assert "Fatigue risk level: low." in captured.out


def test_cli_fail_on_no_data(monkeypatch, capsys) -> None:
    service = HevyService(client=CliClient())
    monkeypatch.setattr("hevy_analytics.cli.build_service", lambda: service)
    monkeypatch.setattr(
        "hevy_analytics.cli._execute",
        lambda _service, _tool, _fn, *args: attach_meta(
            build_error_result(
                NoDataError(
                    "No routines returned by Hevy API.",
                    "Create at least one routine in Hevy and retry.",
                ),
                status="no_data",
            ),
            tool_name="get_routines",
        ),
    )

    exit_code = main(["get-routines", "--fail-on-no-data"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 3
    assert payload["status"] == "no_data"
