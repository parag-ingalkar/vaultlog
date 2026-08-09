from __future__ import annotations

from fastapi import Request


def request_id_from(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def error_body(code: str, message: str, request_id: str | None) -> dict[str, object]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def http_exception_message(detail: object) -> str:
    if isinstance(detail, str):
        return detail
    return str(detail)
