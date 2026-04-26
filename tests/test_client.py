from __future__ import annotations

import httpx
import pytest

from hevy_analytics.client import HevyApiClient
from hevy_analytics.errors import (
    NotFoundError,
    UpstreamAuthError,
    UpstreamRateLimitError,
    UpstreamServerError,
)


def _client(handler: httpx.MockTransport) -> HevyApiClient:
    return HevyApiClient(
        api_key="token",
        base_url="https://example.test",
        transport=handler,
        sleep_fn=lambda _: None,
    )


def test_request_json_retries_429_then_succeeds() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(429, text="rate limit")
        return httpx.Response(200, json={"ok": True})

    client = _client(httpx.MockTransport(handler))

    payload = client.request_json("/endpoint")
    assert payload["ok"] is True
    assert attempts["count"] == 3


def test_request_json_retries_timeout_then_succeeds() -> None:
    attempts = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise httpx.ReadTimeout("timeout")
        return httpx.Response(200, json={"ok": True})

    client = _client(httpx.MockTransport(handler))

    payload = client.request_json("/endpoint")
    assert payload["ok"] is True
    assert attempts["count"] == 3


def test_request_json_401_raises_auth_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(UpstreamAuthError):
        client.request_json("/endpoint")


def test_request_json_403_raises_auth_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(UpstreamAuthError):
        client.request_json("/endpoint")


def test_request_json_404_not_found_raises() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Workout not found")

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(NotFoundError):
        client.request_json("/workouts/abc")


def test_request_json_429_after_retries_raises_rate_limit() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limit")

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(UpstreamRateLimitError):
        client.request_json("/endpoint")


def test_request_json_5xx_after_retries_raises_server_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="service unavailable")

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(UpstreamServerError):
        client.request_json("/endpoint")


def test_request_json_network_error_after_retries_raises_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down", request=request)

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(UpstreamServerError):
        client.request_json("/endpoint")


def test_request_json_non_json_raises_server_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(UpstreamServerError):
        client.request_json("/endpoint")


def test_request_json_non_dict_payload_raises_server_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["unexpected", "shape"])

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(UpstreamServerError):
        client.request_json("/endpoint")


def test_paginate_stops_on_page_not_found_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page")
        if page == "1":
            return httpx.Response(200, json={"page": 1, "page_count": 99, "items": [{"id": "a"}]})
        return httpx.Response(404, text="Page not found")

    client = _client(httpx.MockTransport(handler))

    rows = client.paginate("/items", "items", page_size=10)
    assert rows == [{"id": "a"}]


def test_paginate_raises_on_non_list_payload_key() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"page": 1, "page_count": 1, "items": {"id": "a"}})

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(UpstreamServerError):
        client.paginate("/items", "items", page_size=10)
