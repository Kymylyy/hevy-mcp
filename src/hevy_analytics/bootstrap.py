from __future__ import annotations

import os

from .client import HevyApiClient
from .config import BASE_URL
from .errors import UpstreamAuthError
from .service import HevyService

_SERVICE: HevyService | None = None


def build_service() -> HevyService:
    api_key = os.getenv("HEVY_API_KEY", "").strip()
    if not api_key:
        raise UpstreamAuthError(
            "HEVY_API_KEY is missing.",
            "Set HEVY_API_KEY in the environment before startup.",
        )
    return HevyService(HevyApiClient(api_key=api_key, base_url=BASE_URL))


def get_service() -> HevyService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = build_service()
    return _SERVICE


def close_service(service: HevyService) -> None:
    close = getattr(service.client, "close", None)
    if callable(close):
        close()


def reset_service() -> None:
    global _SERVICE
    if _SERVICE is None:
        return
    close_service(_SERVICE)
    _SERVICE = None
