from __future__ import annotations

from hevy_mcp.errors import ValidationError
from hevy_mcp.response import render_error, render_response


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
