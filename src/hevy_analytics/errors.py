from __future__ import annotations


class HevyAnalyticsError(Exception):
    """Base class for user-safe analytics-level errors."""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class ValidationError(HevyAnalyticsError):
    pass


class NotFoundError(HevyAnalyticsError):
    pass


class UpstreamAuthError(HevyAnalyticsError):
    pass


class UpstreamRateLimitError(HevyAnalyticsError):
    pass


class UpstreamServerError(HevyAnalyticsError):
    pass


class NoDataError(HevyAnalyticsError):
    pass


class PageNotFoundError(Exception):
    pass
