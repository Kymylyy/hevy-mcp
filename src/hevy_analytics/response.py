from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from typing import Any, Literal

from .errors import HevyAnalyticsError, NoDataError

ToolStatus = Literal["ok", "no_data", "error"]


@dataclass(slots=True)
class ToolErrorInfo:
    type: str
    message: str
    hint: str


@dataclass(slots=True)
class ToolMeta:
    tool: str
    generated_at: str


@dataclass(slots=True)
class ToolResult:
    status: ToolStatus
    summary: str
    data_window: str
    details: list[str]
    notes: list[str]
    data: Any = None
    error: ToolErrorInfo | None = None
    meta: ToolMeta | None = None


def build_result(
    summary: str,
    data_window: str,
    details: list[str],
    notes: list[str],
    *,
    data: Any = None,
) -> ToolResult:
    return ToolResult(
        status="ok",
        summary=summary,
        data_window=data_window,
        details=details or ["-"],
        notes=notes or ["-"],
        data=data,
    )


def build_error_result(error: HevyAnalyticsError, *, status: ToolStatus = "error") -> ToolResult:
    hint = error.hint or "Retry with adjusted input."
    return ToolResult(
        status=status,
        summary=f"Error: {error.__class__.__name__} - {error.message}",
        data_window="-",
        details=["- Request could not be completed."],
        notes=[f"- {hint}"],
        data=None,
        error=ToolErrorInfo(
            type=error.__class__.__name__,
            message=error.message,
            hint=error.hint,
        ),
    )


def attach_meta(result: ToolResult, *, tool_name: str) -> ToolResult:
    return replace(
        result,
        meta=ToolMeta(tool=tool_name, generated_at=_generated_at()),
    )


def result_to_dict(result: ToolResult) -> dict[str, Any]:
    return asdict(result)


def render_markdown(result: ToolResult) -> str:
    rendered_details = result.details or ["-"]
    rendered_notes = result.notes or ["-"]
    return "\n".join(
        [
            "## Summary",
            result.summary,
            "",
            "## Data Window",
            result.data_window,
            "",
            "## Details",
            *rendered_details,
            "",
            "## Notes",
            *rendered_notes,
        ]
    )


def render_response(
    summary: str,
    data_window: str,
    details: list[str],
    notes: list[str],
) -> str:
    return render_markdown(build_result(summary, data_window, details, notes))


def render_error(error: HevyAnalyticsError) -> str:
    status: ToolStatus = "no_data" if isinstance(error, NoDataError) else "error"
    return render_markdown(build_error_result(error, status=status))


def _generated_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
