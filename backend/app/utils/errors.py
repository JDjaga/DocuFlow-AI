"""Shared response helpers and application errors.

WHAT THIS FILE DOES
    - AppError: an exception carrying an HTTP status code + safe message
    - small factory functions (`not_found()`, `bad_request()`, ...) so
      every router reports errors in exactly the same JSON shape

WHY IT EXISTS
    Keeps error handling consistent: `{ "detail": "..." }` with the right
    status code, never a Python stack trace or an internal SQL message.

HOW IT CONNECTS
    services raise these -> main.py registers an exception handler ->
    FastAPI returns the JSON response to axios -> frontend shows a toast.
"""


class AppError(Exception):
    """Base error that the API turns into a clean JSON response."""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def bad_request(detail: str) -> AppError:
    return AppError(detail, status_code=400)


def unauthorized(detail: str = "Could not validate credentials.") -> AppError:
    return AppError(detail, status_code=401)


def not_found(detail: str = "Resource not found.") -> AppError:
    return AppError(detail, status_code=404)


def conflict(detail: str) -> AppError:
    return AppError(detail, status_code=409)


def service_unavailable(detail: str) -> AppError:
    return AppError(detail, status_code=503)
