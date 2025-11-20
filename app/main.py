# app/main.py
# App wiring: FastAPI app, session cookie (30 min), and routers.

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.flash import FlashMiddleware
from app.observability import RequestLogMiddleware
from app.routers.auth import router as auth_router
from app.routers.budget import router as budget_router
from app.routers.system import router as system_router

settings = get_settings()

app = FastAPI(title="Personal Accountant", version="0.1.0")

# Session cookie: 30 minutes, works over HTTP (for TestClient/local dev).
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=1800,  # 30 minutes (seconds)
    same_site="lax",
    https_only=False,  # keep False for localhost/tests; set True on HTTPS
)

# Flash messages and request logging (must come AFTER SessionMiddleware)
app.add_middleware(FlashMiddleware)
app.add_middleware(RequestLogMiddleware)

# Routers
app.include_router(system_router)
app.include_router(auth_router)
app.include_router(budget_router)
