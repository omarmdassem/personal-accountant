# app/security.py
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from fastapi.requests import Request
from passlib.context import CryptContext

# Password hashing context (bcrypt by default)
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ------------ Password helpers ------------


def hash_password(plain: str) -> str:
    """Return a secure hash for a plaintext password."""
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    return _pwd.verify(plain, hashed)


# ------------ Session / Auth helpers ------------


def get_user_id_from_session(request: Request) -> Optional[int]:
    """
    Read user_id from the session (if present). Returns int or None.
    """
    try:
        uid = request.session.get("user_id")  # set during /auth/signin
    except Exception:
        uid = None
    return int(uid) if uid is not None else None


def require_user_id(request: Request) -> int:
    """
    Ensure the request has a logged-in user. If not, flash a message and 303-redirect to signin.
    Usage (inside route):  user_id = require_user_id(request)
    """
    uid = get_user_id_from_session(request)
    if uid is None:
        # Try to flash politely; avoid import cycles by importing here.
        try:
            from app.flash import add_flash  # local import to avoid cycles

            add_flash(request, "warning", "Please sign in to continue.")
        except Exception:
            pass
        # Redirect to signin
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/signin"},
        )
    return uid


__all__ = [
    "hash_password",
    "verify_password",
    "get_user_id_from_session",
    "require_user_id",
]
