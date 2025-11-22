# app/flash.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

_FLASH_KEY = "_flashes"  # where we store flashes inside the session


def _get_session_like(request: Request) -> Dict[str, Any]:
    """
    Return a mutable mapping to store flashes.
    Prefer request.session if SessionMiddleware is installed,
    otherwise fall back to a per-request dict (no persistence).
    """
    if "session" in request.scope:
        # SessionMiddleware installed → safe to use request.session
        return request.session  # type: ignore[return-value]

    # Fallback: per-request store so templates can still read flashes
    if not hasattr(request.state, "_flash_fallback"):
        request.state._flash_fallback = {}
    return request.state._flash_fallback


def flash(request: Request, message: str, category: str = "info") -> None:
    """
    Queue a flash message for the next response.
    Stored as list of (category, message) tuples.
    """
    store = _get_session_like(request)
    items: List[Tuple[str, str]] = list(store.get(_FLASH_KEY, []))
    items.append((category, message))
    store[_FLASH_KEY] = items


# Backwards compat alias (some modules might import add_flash)
add_flash = flash


def _pop_flashes(request: Request) -> List[Tuple[str, str]]:
    """
    Remove and return any queued flashes from the session/store.
    """
    store = _get_session_like(request)
    items: List[Tuple[str, str]] = list(store.get(_FLASH_KEY, []))
    if items:
        # clear after reading so they don't show twice
        store[_FLASH_KEY] = []
    return items


class FlashMiddleware(BaseHTTPMiddleware):
    """
    Makes flashes available at request.state.flashes for templates.
    Also ensures we don't crash if SessionMiddleware isn't present yet.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Pull flashes into request.state before the endpoint renders a template
        request.state.flashes = _pop_flashes(request)
        response = await call_next(request)
        return response
