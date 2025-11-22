# app/main.py
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.flash import FlashMiddleware
from app.observability import RequestLogMiddleware
from app.routers.auth import router as auth_router
from app.routers.budget import router as budget_router
from app.routers.system import router as system_router
from app.routers.transactions import router as transactions_router

settings = get_settings()
app = FastAPI(title="Personal Accountant", version="0.1.0")
templates = Jinja2Templates(directory="app/templates")

# --- Middleware order matters: session first ---
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=1800,  # 30 minutes
    same_site="lax",
)
app.add_middleware(RequestLogMiddleware)
app.add_middleware(FlashMiddleware)

# --- Routers ---
app.include_router(system_router)
app.include_router(auth_router)
app.include_router(budget_router)
app.include_router(transactions_router)


# --- Home page ---
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
