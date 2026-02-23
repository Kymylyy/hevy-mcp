from __future__ import annotations


class HevyMcpError(Exception):
    """Base class for user-safe, tool-level errors."""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class ValidationError(HevyMcpError):
    pass


class NotFoundError(HevyMcpError):
    pass


class UpstreamAuthError(HevyMcpError):
    pass


class UpstreamRateLimitError(HevyMcpError):
    pass


class UpstreamServerError(HevyMcpError):
    pass


class NoDataError(HevyMcpError):
    pass


class PageNotFoundError(Exception):
    pass
