# app/routers/system.py
from pathlib import Path  # build a safe path to templates

from fastapi import APIRouter  # Request lets us pass context to templates
from fastapi import Request
from fastapi.responses import PlainTextResponse  # still used for /healthz
from fastapi.templating import Jinja2Templates  # template renderer

router = APIRouter()  # group of routes

# point to the templates folder: app/templates (system.py is in app/routers)
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"  # parents[1] == app/
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))  # create renderer


@router.get("/healthz", response_class=PlainTextResponse)  # tiny health check
def healthz():
    return "ok"


@router.get("/")  # home page route
def home(request: Request):  # Request is required by Jinja2Templates
    # TemplateResponse renders app/templates/index.html
    # we must pass {"request": request} for Jinja internals
    return templates.TemplateResponse("index.html", {"request": request})
