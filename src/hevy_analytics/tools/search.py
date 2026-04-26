from __future__ import annotations

from typing import Any

from ..config import SEARCH_HISTORY_LOOKBACK_DAYS, SEARCH_MATCH_CANDIDATES
from ..errors import NotFoundError
from ..response import ToolResult, build_result
from ..service import HevyService
from ..validation import validate_name
from ._shared import rerank_matches_with_history


def search_exercise(service: HevyService, name: str) -> ToolResult:
    query = validate_name(name)
    candidates = service.rank_templates(query, limit=SEARCH_MATCH_CANDIDATES)
    usage = service.load_recent_template_usage(SEARCH_HISTORY_LOOKBACK_DAYS)
    matches = rerank_matches_with_history(query, candidates, usage)[:5]
    if not matches:
        raise NotFoundError(
            f"No exercise found for '{query}'.",
            "Use a broader keyword, for example 'squat' instead of a long variant.",
        )

    details = [
        "| title | id | type | primary muscle | equipment | recent sets | custom |",
        "|---|---|---|---|---|---|---|",
    ]
    for match in matches:
        recent_sets = usage.get(str(match.get("id", "")), 0)
        details.append(
            (
                "| {title} | {id} | {type} | {primary} | {equipment} | {recent_sets} | {custom} |"
            ).format(
                title=match.get("title", "-"),
                id=match.get("id", "-"),
                type=match.get("type", "-"),
                primary=match.get("primary_muscle_group", "-"),
                equipment=match.get("equipment", "-"),
                recent_sets=recent_sets if recent_sets else "-",
                custom="yes" if match.get("is_custom") else "no",
            )
        )

    top = matches[0]
    summary = (
        f"Found {len(matches)} match(es) for '{query}'. "
        f"Best match: {top.get('title', 'unknown')} ({top.get('id', '-')})."
    )
    notes = [
        (
            "- Matching order: exact match -> recent user history boost "
            f"({SEARCH_HISTORY_LOOKBACK_DAYS}d) -> text similarity (difflib)."
        )
    ]
    data: dict[str, Any] = {
        "query": query,
        "matches": [
            {
                "id": str(match.get("id", "")),
                "title": str(match.get("title", "")),
                "type": match.get("type"),
                "primary_muscle_group": match.get("primary_muscle_group"),
                "equipment": match.get("equipment"),
                "recent_sets": usage.get(str(match.get("id", "")), 0),
                "is_custom": bool(match.get("is_custom")),
            }
            for match in matches
        ],
    }
    return build_result(
        summary,
        "Exercise catalog snapshot (cached up to 12h).",
        details,
        notes,
        data=data,
    )
