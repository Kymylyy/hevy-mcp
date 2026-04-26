from __future__ import annotations

import json
import logging
from typing import Any


class ToolEventLogger:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _default_logger()

    def log_tool_call(
        self,
        tool_name: str,
        duration_ms: int,
        http_calls: int,
        cache_hits: int,
        result_status: str,
    ) -> None:
        event: dict[str, Any] = {
            "tool_name": tool_name,
            "duration_ms": duration_ms,
            "http_calls": http_calls,
            "cache_hits": cache_hits,
            "result_status": result_status,
        }
        self._logger.info(json.dumps(event))


_DEFAULT_LOGGER: logging.Logger | None = None


def _default_logger() -> logging.Logger:
    global _DEFAULT_LOGGER
    if _DEFAULT_LOGGER is not None:
        return _DEFAULT_LOGGER

    logger = logging.getLogger("hevy_analytics.tool_events")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    _DEFAULT_LOGGER = logger
    return logger
