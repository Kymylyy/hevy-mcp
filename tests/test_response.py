from __future__ import annotations

from hevy_analytics.errors import NoDataError, ValidationError
from hevy_analytics.response import (
    attach_meta,
    build_error_result,
    build_result,
    render_error,
    render_markdown,
    render_response,
    result_to_dict,
)


def test_render_response_contract_order_is_stable() -> None:
    output = render_response(
        summary="summary text",
        data_window="window text",
        details=["- detail one", "- detail two"],
        notes=["- note one"],
    )

    lines = output.splitlines()
    assert lines[0] == "## Summary"
    assert lines[3] == "## Data Window"
    assert lines[6] == "## Details"
    assert lines[10] == "## Notes"


def test_render_error_contains_error_class_message_and_hint() -> None:
    error = ValidationError("days must be in range 1..365.", "Choose a value between 1 and 365.")

    output = render_error(error)

    assert "Error: ValidationError - days must be in range 1..365." in output
    assert "- Request could not be completed." in output
    assert "- Choose a value between 1 and 365." in output


def test_build_result_and_attach_meta_produce_json_ready_payload() -> None:
    result = attach_meta(
        build_result(
            summary="summary text",
            data_window="window text",
            details=["- detail"],
            notes=["- note"],
            data={"value": 1},
        ),
        tool_name="weekly_volume",
    )

    payload = result_to_dict(result)

    assert payload["status"] == "ok"
    assert payload["meta"]["tool"] == "weekly_volume"
    assert payload["data"]["value"] == 1


def test_no_data_result_renders_like_legacy_markdown_error() -> None:
    error = NoDataError("No workouts found.", "Increase days and retry.")

    result = build_error_result(error, status="no_data")
    output = render_markdown(result)

    assert result.status == "no_data"
    assert "Error: NoDataError - No workouts found." in output
