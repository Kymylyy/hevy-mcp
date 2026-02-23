import httpx
import pytest

from hevy_mcp.client import HevyApiClient
from hevy_mcp.errors import NotFoundError


def test_request_json_retries_429_then_succeeds() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(429, text="rate limit")
        return httpx.Response(200, json={"ok": True})

    client = HevyApiClient(
        api_key="token",
        base_url="https://example.test",
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    )

    payload = client.request_json("/endpoint")
    assert payload["ok"] is True
    assert attempts["count"] == 3


def test_paginate_stops_on_page_not_found_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page")
        if page == "1":
            return httpx.Response(200, json={"page": 1, "page_count": 99, "items": [{"id": "a"}]})
        return httpx.Response(404, text="Page not found")

    client = HevyApiClient(
        api_key="token",
        base_url="https://example.test",
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    )

    rows = client.paginate("/items", "items", page_size=10)
    assert rows == [{"id": "a"}]


def test_request_json_404_not_found_raises() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Workout not found")

    client = HevyApiClient(
        api_key="token",
        base_url="https://example.test",
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    )

    with pytest.raises(NotFoundError):
        client.request_json("/workouts/abc")
