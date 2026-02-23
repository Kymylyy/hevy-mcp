from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from datetime import timedelta
from difflib import SequenceMatcher
from typing import Any, cast

from .cache import TTLCache
from .client import HevyApiClient
from .config import HISTORY_TTL_SECONDS, SEARCH_TTL_SECONDS, TEMPLATES_TTL_SECONDS
from .errors import HevyMcpError, UpstreamServerError, ValidationError
from .response import render_error
from .utils import normalize_text, utc_now


class HevyService:
    def __init__(self, client: HevyApiClient) -> None:
        self.client = client
        self._templates_cache = TTLCache()
        self._history_cache = TTLCache()
        self._search_cache = TTLCache()
        self.cache_hits = 0

    def execute(self, tool_name: str, fn: Callable[..., str], *args: Any) -> str:
        started = time.perf_counter()
        req_before = self.client.request_count
        self.cache_hits = 0
        status = "ok"

        try:
            return fn(*args)
        except HevyMcpError as exc:
            status = "error"
            return render_error(exc)
        except Exception:
            status = "error"
            return render_error(
                UpstreamServerError(
                    "Unexpected tool failure.",
                    "Retry. If this repeats, inspect server logs for stack traces.",
                )
            )
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            request_delta = self.client.request_count - req_before
            self._log_tool_call(tool_name, duration_ms, request_delta, self.cache_hits, status)

    def load_templates(self) -> list[dict[str, Any]]:
        cached = self._templates_cache.get("all")
        if isinstance(cached, list):
            self.cache_hits += 1
            return cached

        templates = self.client.paginate("/exercise_templates", "exercise_templates", page_size=100)
        self._templates_cache.set("all", templates, ttl_seconds=TEMPLATES_TTL_SECONDS)
        return templates

    def load_history(self, template_id: str) -> list[dict[str, Any]]:
        cache_key = f"history:{template_id}"
        cached = self._history_cache.get(cache_key)
        if isinstance(cached, list):
            self.cache_hits += 1
            return cached

        rows = self.client.get_exercise_history(template_id)
        self._history_cache.set(cache_key, rows, ttl_seconds=HISTORY_TTL_SECONDS)
        return rows

    def rank_templates(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if limit < 1:
            return []
        normalized = normalize_text(query)
        cache_key = f"search:{normalized}:{limit}"
        cached = self._search_cache.get(cache_key)
        if isinstance(cached, list):
            self.cache_hits += 1
            return cached

        ranked: list[tuple[int, float, str, dict[str, Any]]] = []
        for template in self.load_templates():
            title = template.get("title")
            if not isinstance(title, str):
                continue
            norm_title = normalize_text(title)

            if norm_title == normalized:
                ranked.append((0, 1.0, title.lower(), template))
                continue
            if normalized and normalized in norm_title:
                score = SequenceMatcher(None, normalized, norm_title).ratio()
                ranked.append((1, score, title.lower(), template))
                continue
            score = SequenceMatcher(None, normalized, norm_title).ratio()
            if score >= 0.45:
                ranked.append((2, score, title.lower(), template))

        ranked.sort(key=lambda row: (row[0], -row[1], row[2]))
        matches = [row[3] for row in ranked[:limit]]
        self._search_cache.set(cache_key, matches, ttl_seconds=SEARCH_TTL_SECONDS)
        return matches

    def load_recent_template_usage(self, days: int) -> dict[str, int]:
        cache_key = f"template_usage:{days}"
        cached = self._history_cache.get(cache_key)
        if isinstance(cached, dict):
            self.cache_hits += 1
            return cast(dict[str, int], cached)

        start = utc_now() - timedelta(days=days)
        workouts = self.client.get_workouts_since(start)
        usage: dict[str, int] = {}

        for workout in workouts:
            exercises = workout.get("exercises", [])
            if not isinstance(exercises, list):
                continue
            for exercise in exercises:
                if not isinstance(exercise, dict):
                    continue
                template_id = str(exercise.get("exercise_template_id", "")).strip()
                if not template_id:
                    continue

                bump = 1
                set_rows = exercise.get("sets", [])
                if isinstance(set_rows, list):
                    counted = sum(1 for row in set_rows if isinstance(row, dict))
                    if counted > 0:
                        bump = counted
                usage[template_id] = usage.get(template_id, 0) + bump

        self._history_cache.set(cache_key, usage, ttl_seconds=HISTORY_TTL_SECONDS)
        return usage

    @staticmethod
    def validate_name(value: Any) -> str:
        if not isinstance(value, str):
            raise ValidationError("name must be a string.", "Pass a non-empty exercise name.")
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValidationError("name is too short.", "Provide at least two characters.")
        return cleaned

    @staticmethod
    def validate_days(value: Any) -> int:
        if not isinstance(value, int):
            raise ValidationError("days must be an integer.", "Use an integer between 1 and 365.")
        if value < 1 or value > 365:
            raise ValidationError(
                "days must be in range 1..365.",
                "Choose a value between 1 and 365.",
            )
        return value

    @staticmethod
    def validate_weeks(value: Any) -> int:
        if not isinstance(value, int):
            raise ValidationError("weeks must be an integer.", "Use an integer between 1 and 52.")
        if value < 1 or value > 52:
            raise ValidationError(
                "weeks must be in range 1..52.",
                "Choose a value between 1 and 52.",
            )
        return value

    @staticmethod
    def _log_tool_call(
        tool_name: str,
        duration_ms: int,
        http_calls: int,
        cache_hits: int,
        result_status: str,
    ) -> None:
        event = {
            "tool_name": tool_name,
            "duration_ms": duration_ms,
            "http_calls": http_calls,
            "cache_hits": cache_hits,
            "result_status": result_status,
        }
        print(json.dumps(event), file=sys.stderr, flush=True)
