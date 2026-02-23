from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from .config import WORKING_SET_TYPES


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_iso_datetime(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized).astimezone(UTC)


def normalize_text(value: str) -> str:
    collapsed = " ".join(value.lower().strip().split())
    return "".join(ch for ch in collapsed if ch.isalnum() or ch.isspace())


def format_number(value: float, decimals: int = 1) -> str:
    rendered = f"{value:.{decimals}f}"
    return rendered.rstrip("0").rstrip(".")


def format_set(set_entry: Mapping[str, Any]) -> str:
    weight = set_entry.get("weight_kg")
    reps = set_entry.get("reps")
    distance = set_entry.get("distance_meters")
    duration = set_entry.get("duration_seconds")

    if isinstance(weight, (int, float)) and isinstance(reps, (int, float)):
        return f"{format_number(float(weight))}kg x {int(reps)}"
    if isinstance(reps, (int, float)):
        return f"{int(reps)} reps"
    if isinstance(distance, (int, float)) and isinstance(duration, (int, float)):
        return f"{int(distance)}m in {int(duration)}s"
    if isinstance(duration, (int, float)):
        return f"{int(duration)}s"
    return "tracked set"


def estimate_e1rm(weight: Any, reps: Any) -> float | None:
    if not isinstance(weight, (int, float)) or not isinstance(reps, (int, float)):
        return None
    if reps <= 0:
        return None
    return float(weight) * (1 + float(reps) / 30.0)


def is_working_set(set_type: Any) -> bool:
    return isinstance(set_type, str) and set_type in WORKING_SET_TYPES
