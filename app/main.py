from pathlib import Path  # helps build file system paths safely

from fastapi import FastAPI  # the web app framework
from fastapi.staticfiles import StaticFiles  # serves files like CSS/JS/images
from starlette.middleware.sessions import (
    SessionMiddleware,  # adds secure cookie sessions
)

from app.config import get_settings  # our function to read settings from .env
from app.flash import FlashMiddleware
from app.observability import RequestLogMiddleware
from app.routers import budget
from app.routers.auth import router as auth_router
from app.routers.system import router as system_router

settings = get_settings()  # read and cache config (secret key, db url, etc.)

app = FastAPI()  # create the web application object (think: the "server" you talk to)

# add session support: this sets/reads a secure cookie so we can remember logged-in users
# - secret_key: used to sign the cookie so it can't be forged
# - session_cookie: the cookie's name in the browser
# If you change secret_key: all users will be logged out (cookies become invalid)
# If you change session_cookie: the name changes; old cookie won't be found -> logged out once
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie=settings.session_cookie,
)

# figure out the path to the "app" folder; we use it to point to the /static directory
BASE_DIR = Path(__file__).resolve().parent

# expose a URL "/static/..." that serves files from app/static (even if it's empty now)
# If you change "/static" to something else, update your HTML links to match
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# include_router = "plug this group of endpoints into the app"
# If you change prefix="/api", all routes inside get that prefix (e.g., /api/healthz)
app.include_router(system_router)  # no prefix for now
app.include_router(auth_router, prefix="/auth")
app.include_router(budget.router)


# ⬇️ Add this FIRST (so request.session is available to others)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=1800,  # 30 minutes
    same_site="lax",  # good default for forms
    # https_only=False  # keep False on localhost; True when you serve HTTPS
)

# Then your other middlewares
app.add_middleware(FlashMiddleware)
app.add_middleware(RequestLogMiddleware)
