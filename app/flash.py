# app/flash.py
# Minimal "flash message" support: add_flash() stores a note in the session.
# FlashMiddleware moves notes into request.state.flashes and clears the session copy.

from typing import Literal

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

FlashKind = Literal["success", "error", "info", "warning"]


def add_flash(request: Request, message: str, kind: FlashKind = "info") -> None:
    """Store a one-time message in the session; shown after redirect."""
    try:
        flashes = request.session.get("flashes") or []
        flashes.append({"kind": kind, "message": message})
        request.session["flashes"] = flashes
    except AssertionError:
        # SessionMiddleware missing → silently skip (shouldn't happen in normal flow)
        pass


class FlashMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Pull flashes out of session so they appear once
        try:
            flashes = request.session.pop("flashes", [])
        except AssertionError:
            flashes = []
        request.state.flashes = flashes  # available to templates via "request"
        response = await call_next(request)
        return response
