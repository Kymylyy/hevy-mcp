from __future__ import annotations

from collections import Counter
from typing import Any

from ..utils import format_number, format_set, normalize_text


def split_label(title: str) -> str:
    normalized = title.lower()
    if "upper" in normalized:
        return "Upper"
    if "lower" in normalized:
        return "Lower"
    if "full body" in normalized or "full" in normalized:
        return "Full Body"
    if "arm" in normalized or "delt" in normalized or "shoulder" in normalized:
        return "Arms/Delts"
    return "Other"


def rerank_matches_with_history(
    query: str,
    matches: list[dict[str, Any]],
    usage_by_template: dict[str, int],
) -> list[dict[str, Any]]:
    normalized_query = normalize_text(query)
    scored: list[tuple[int, int, int, dict[str, Any]]] = []

    for index, match in enumerate(matches):
        title = str(match.get("title", ""))
        normalized_title = normalize_text(title)
        template_id = str(match.get("id", ""))
        usage = usage_by_template.get(template_id, 0)

        if normalized_title == normalized_query:
            group = 0
        elif usage > 0:
            group = 1
        else:
            group = 2
        scored.append((group, -usage, index, match))

    scored.sort(key=lambda row: (row[0], row[1], row[2]))
    return [row[3] for row in scored]


def summarize_set_scheme(set_rows: list[Any]) -> str:
    rendered: list[str] = []
    for row in set_rows:
        if not isinstance(row, dict):
            continue
        rendered.append(render_set_detail(row))
    if not rendered:
        return "no set plan"

    grouped: Counter[str] = Counter(rendered)
    chunks: list[str] = []
    for label in rendered:
        count = grouped.pop(label, 0)
        if count <= 0:
            continue
        chunks.append(f"{count}x {label}")
    return ", ".join(chunks)


def render_set_detail(set_row: dict[str, Any]) -> str:
    label = format_set(set_row)

    set_type = set_row.get("type")
    reps = set_row.get("reps")
    if set_type == "failure" and isinstance(reps, (int, float)):
        rep_text = str(int(reps))
        if label.endswith(rep_text):
            label = f"{label}+"

    if isinstance(set_type, str) and set_type != "normal":
        label = f"{label} [{set_type}]"

    extras: list[str] = []
    rir = set_row.get("rir")
    if isinstance(rir, (int, float)):
        extras.append(f"RIR {format_number(float(rir), 1)}")
    rest_seconds = set_row.get("rest_seconds")
    if isinstance(rest_seconds, (int, float)):
        extras.append(f"rest {int(rest_seconds)}s")

    if extras:
        label = f"{label} ({', '.join(extras)})"
    return label
