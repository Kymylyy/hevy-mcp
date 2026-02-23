from __future__ import annotations

from typing import Any

from .errors import ValidationError


def validate_name(value: Any) -> str:
    if not isinstance(value, str):
        raise ValidationError("name must be a string.", "Pass a non-empty exercise name.")
    cleaned = value.strip()
    if len(cleaned) < 2:
        raise ValidationError("name is too short.", "Provide at least two characters.")
    return cleaned


def validate_days(value: Any) -> int:
    if not isinstance(value, int):
        raise ValidationError("days must be an integer.", "Use an integer between 1 and 365.")
    if value < 1 or value > 365:
        raise ValidationError(
            "days must be in range 1..365.",
            "Choose a value between 1 and 365.",
        )
    return value


def validate_weeks(value: Any) -> int:
    if not isinstance(value, int):
        raise ValidationError("weeks must be an integer.", "Use an integer between 1 and 52.")
    if value < 1 or value > 52:
        raise ValidationError(
            "weeks must be in range 1..52.",
            "Choose a value between 1 and 52.",
        )
    return value
