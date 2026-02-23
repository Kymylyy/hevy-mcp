from __future__ import annotations

import random
import time
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

import httpx

from .config import MAX_RETRIES, RETRY_DELAYS
from .errors import (
    NotFoundError,
    PageNotFoundError,
    UpstreamAuthError,
    UpstreamRateLimitError,
    UpstreamServerError,
)
from .utils import parse_iso_datetime


class HevyApiClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        transport: httpx.BaseTransport | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._sleep_fn = sleep_fn
        self._client = httpx.Client(
            base_url=base_url,
            headers={"api-key": api_key},
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=30.0),
            transport=transport,
        )
        self.request_count = 0

    def close(self) -> None:
        self._client.close()

    def request_json(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        treat_404_as_page_end: bool = False,
    ) -> dict[str, Any]:
        for attempt in range(MAX_RETRIES + 1):
            self.request_count += 1
            try:
                response = self._client.get(path, params=params)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < MAX_RETRIES:
                    self._backoff(attempt)
                    continue
                raise UpstreamServerError(
                    "Hevy API request failed after retries.",
                    "Retry in a moment. If this repeats, check network availability.",
                ) from exc

            status = response.status_code
            if status in {401, 403}:
                raise UpstreamAuthError(
                    "Hevy API authentication failed.",
                    "Verify HEVY_API_KEY and restart the MCP server.",
                )

            if status == 404:
                text_body = response.text.strip()
                if treat_404_as_page_end and "page not found" in text_body.lower():
                    raise PageNotFoundError(text_body)
                raise NotFoundError(
                    "Requested Hevy resource was not found.",
                    "Check identifiers and try again.",
                )

            if status == 429:
                if attempt < MAX_RETRIES:
                    self._backoff(attempt)
                    continue
                raise UpstreamRateLimitError(
                    "Hevy API rate limit reached.",
                    "Retry later or narrow the requested time window.",
                )

            if status >= 500:
                if attempt < MAX_RETRIES:
                    self._backoff(attempt)
                    continue
                raise UpstreamServerError(
                    f"Hevy API returned {status} after retries.",
                    "Retry later. If this persists, upstream may be degraded.",
                )

            if status >= 400:
                raise UpstreamServerError(
                    f"Unexpected Hevy API error: HTTP {status}.",
                    "Retry with a smaller request or validate the input.",
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise UpstreamServerError(
                    "Hevy API returned non-JSON payload.",
                    "Retry the request. If it repeats, inspect upstream API behavior.",
                ) from exc

            if not isinstance(payload, dict):
                raise UpstreamServerError(
                    "Hevy API payload has unexpected shape.",
                    "Retry later. If repeated, update parser mapping.",
                )
            return payload

        raise UpstreamServerError("Hevy API request failed after retries.", "Retry in a moment.")

    def paginate(
        self,
        path: str,
        key: str,
        page_size: int,
        params: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            req: dict[str, Any] = {"page": page, "pageSize": page_size}
            if params:
                req.update(dict(params))
            try:
                payload = self.request_json(path, req, treat_404_as_page_end=True)
            except PageNotFoundError:
                break

            raw_items = payload.get(key, [])
            if not isinstance(raw_items, list):
                raise UpstreamServerError(
                    f"Expected list payload under '{key}'.",
                    "Retry the call. If this persists, update parser mapping.",
                )

            rows.extend(item for item in raw_items if isinstance(item, dict))
            page_count = payload.get("page_count", page)
            if not isinstance(page_count, int) or page >= page_count:
                break
            page += 1
        return rows

    def get_workouts_since(self, start_time: datetime) -> list[dict[str, Any]]:
        workouts: list[dict[str, Any]] = []
        page = 1
        while True:
            try:
                payload = self.request_json(
                    "/workouts",
                    {"page": page, "pageSize": 10},
                    treat_404_as_page_end=True,
                )
            except PageNotFoundError:
                break

            raw_workouts = payload.get("workouts", [])
            if not isinstance(raw_workouts, list) or not raw_workouts:
                break

            oldest_start: datetime | None = None
            for workout in raw_workouts:
                if not isinstance(workout, dict):
                    continue
                start_raw = workout.get("start_time")
                if not isinstance(start_raw, str):
                    continue
                start_at = parse_iso_datetime(start_raw)
                oldest_start = start_at if oldest_start is None else min(oldest_start, start_at)
                if start_at >= start_time:
                    workouts.append(workout)

            if oldest_start is not None and oldest_start < start_time:
                break

            page_count = payload.get("page_count", page)
            if not isinstance(page_count, int) or page >= page_count:
                break
            page += 1
        return workouts

    def get_exercise_history(self, template_id: str) -> list[dict[str, Any]]:
        payload = self.request_json(f"/exercise_history/{template_id}")
        raw_rows = payload.get("exercise_history", [])
        if not isinstance(raw_rows, list):
            raise UpstreamServerError(
                "Unexpected exercise_history payload shape.",
                "Retry later. If repeated, update parser for exercise history endpoint.",
            )
        return [row for row in raw_rows if isinstance(row, dict)]

    def get_routine_folders(self) -> list[dict[str, Any]]:
        payload = self.request_json("/routine_folders")
        raw_folders = payload.get("routine_folders", payload.get("folders", []))
        if not isinstance(raw_folders, list):
            return []
        return [folder for folder in raw_folders if isinstance(folder, dict)]

    def _backoff(self, attempt: int) -> None:
        delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)] + random.uniform(0.0, 0.2)
        self._sleep_fn(delay)
