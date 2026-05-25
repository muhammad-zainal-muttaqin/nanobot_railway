"""Telegram Bot API error classes."""

from __future__ import annotations


class BadRequest(Exception):
    pass


class NetworkError(Exception):
    pass


class TimedOut(NetworkError):
    pass


class RetryAfter(BadRequest):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Flood control: retry after {retry_after}s")


class Conflict(Exception):
    pass


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


_HTTP_STATUS_ERROR_MAP: dict[int, type[Exception]] = {
    400: BadRequest,
    403: Forbidden,
    404: NotFound,
    409: Conflict,
}


def raise_for_status(status_code: int, description: str, parameters: dict | None = None) -> None:
    if status_code < 400:
        return
    cls = _HTTP_STATUS_ERROR_MAP.get(status_code, BadRequest)
    if parameters and "retry_after" in parameters:
        raise RetryAfter(float(parameters["retry_after"]))
    raise cls(f"{status_code}: {description}")
