from __future__ import annotations

import os
from typing import Any

from .client import HevyApiClient
from .config import BASE_URL
from .errors import UpstreamAuthError
from .service import HevyService
from .tools import (
    exercise_progression,
    fatigue_check,
    get_routines,
    recent_workouts,
    search_exercise,
    suggest_accessories,
    top_exercises,
    training_log,
    weekly_volume,
)

try:
    from fastmcp import FastMCP as _FastMCP
except ModuleNotFoundError:  # pragma: no cover
    FastMCP: Any = None
else:
    FastMCP = _FastMCP


_SERVICE: HevyService | None = None


def build_service() -> HevyService:
    api_key = os.getenv("HEVY_API_KEY", "").strip()
    if not api_key:
        raise UpstreamAuthError(
            "HEVY_API_KEY is missing.",
            "Set HEVY_API_KEY in your MCP server environment before startup.",
        )
    return HevyService(HevyApiClient(api_key=api_key, base_url=BASE_URL))


def get_service() -> HevyService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = build_service()
    return _SERVICE


def create_mcp_server() -> Any:
    if FastMCP is None:
        raise RuntimeError("fastmcp is not installed. Install dependencies before running server.")

    mcp = FastMCP("hevy")

    @mcp.tool()
    def tool_search_exercise(name: str) -> str:
        service = get_service()
        return service.execute(
            "search_exercise",
            lambda query: search_exercise(service, query),
            name,
        )

    @mcp.tool()
    def tool_exercise_progression(name: str, weeks: int = 12) -> str:
        service = get_service()
        return service.execute(
            "exercise_progression",
            lambda query, w: exercise_progression(service, query, w),
            name,
            weeks,
        )

    @mcp.tool()
    def tool_recent_workouts(days: int = 7) -> str:
        service = get_service()
        return service.execute("recent_workouts", lambda d: recent_workouts(service, d), days)

    @mcp.tool()
    def tool_weekly_volume(weeks: int = 4) -> str:
        service = get_service()
        return service.execute("weekly_volume", lambda w: weekly_volume(service, w), weeks)

    @mcp.tool()
    def tool_fatigue_check() -> str:
        service = get_service()
        return service.execute("fatigue_check", lambda: fatigue_check(service))

    @mcp.tool()
    def tool_suggest_accessories() -> str:
        service = get_service()
        return service.execute("suggest_accessories", lambda: suggest_accessories(service))

    @mcp.tool()
    def tool_training_log(days: int = 30) -> str:
        service = get_service()
        return service.execute("training_log", lambda d: training_log(service, d), days)

    @mcp.tool()
    def tool_top_exercises(days: int = 30, limit: int = 5) -> str:
        service = get_service()
        return service.execute(
            "top_exercises",
            lambda d, n: top_exercises(service, d, n),
            days,
            limit,
        )

    @mcp.tool()
    def tool_get_routines() -> str:
        service = get_service()
        return service.execute("get_routines", lambda: get_routines(service))

    return mcp


def main() -> None:
    server = create_mcp_server()
    server.run()


if __name__ == "__main__":
    main()
