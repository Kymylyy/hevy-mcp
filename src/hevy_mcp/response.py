from __future__ import annotations

from .errors import HevyMcpError


def render_response(
    summary: str,
    data_window: str,
    details: list[str],
    notes: list[str],
) -> str:
    rendered_details = details or ["-"]
    rendered_notes = notes or ["-"]
    return "\n".join(
        [
            "## Summary",
            summary,
            "",
            "## Data Window",
            data_window,
            "",
            "## Details",
            *rendered_details,
            "",
            "## Notes",
            *rendered_notes,
        ]
    )


def render_error(error: HevyMcpError) -> str:
    hint = f"- {error.hint}" if error.hint else "- Retry with adjusted input."
    return render_response(
        summary=f"Error: {error.__class__.__name__} - {error.message}",
        data_window="-",
        details=["- Request could not be completed."],
        notes=[hint],
    )
