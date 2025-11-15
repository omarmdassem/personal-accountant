# app/routers/auth.py
# Zweck: Benutzer anlegen (Signup), anmelden (Signin), abmelden (Signout).
# Wir benutzen: Sessions, CSRF, Passwort-Hashing, DB-Session.
from pathlib import Path  # Pfad zu /app/templates

from fastapi import (  # Router, Request, DI für Form-Felder
    APIRouter,
    Depends,
    Form,
    Request,
)
from fastapi.responses import RedirectResponse  # für Weiterleitungen nach Erfolg
from fastapi.templating import Jinja2Templates  # um Jinja-Templates zu rendern
from sqlalchemy.exc import IntegrityError  # wenn E-Mail unique verletzt wird
from sqlmodel import Session, select  # DB-Session und Select-Query

from app.db import get_session  # liefert kurzlebige DB-Session
from app.models import User  # unser User-Model
from app.security import (  # Security-Helfer
    hash_password,
    issue_csrf_token,
    validate_csrf,
    verify_password,
)

router = APIRouter()  # Gruppe: /auth/* Endpunkte

# Templates-Ordner bestimmen (app/templates)
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/signup")  # Signup-Form anzeigen (GET)
async def signup_form(request: Request):
    # CSRF-Token erzeugen und im Template einbetten
    token = issue_csrf_token(request)
    return templates.TemplateResponse(
        "auth/signup.html", {"request": request, "csrf_token": token, "error": None}
    )


@router.post("/signup")  # Signup absenden (POST)
async def signup_submit(
    request: Request,
    email: str = Form(...),  # Pflicht-Feld aus <form>
    password: str = Form(...),  # Pflicht-Feld aus <form>
    csrf_token: str = Form(...),  # verstecktes CSRF-Feld
    session: Session = Depends(get_session),  # DB-Session für diese Anfrage
):
    # CSRF prüfen: falls falsch/leer -> Formular neu mit Fehler
    if not validate_csrf(request, csrf_token):
        token = issue_csrf_token(request)
        return templates.TemplateResponse(
            "auth/signup.html",
            {
                "request": request,
                "csrf_token": token,
                "error": "CSRF ungültig. Bitte erneut senden.",
            },
            status_code=400,
        )

    # Existiert E-Mail schon? (freundlicher als nur IntegrityError)
    exists = session.exec(select(User).where(User.email == email)).first()
    if exists:
        token = issue_csrf_token(request)
        return templates.TemplateResponse(
            "auth/signup.html",
            {
                "request": request,
                "csrf_token": token,
                "error": "E-Mail bereits registriert.",
            },
            status_code=400,
        )

    # User anlegen: Passwort sicher hashen
    user = User(email=email, hashed_password=hash_password(password))
    try:
        session.add(user)
        session.commit()
        session.refresh(user)  # ID vom DB-Insert holen
    except IntegrityError:
        session.rollback()
        token = issue_csrf_token(request)
        return templates.TemplateResponse(
            "auth/signup.html",
            {
                "request": request,
                "csrf_token": token,
                "error": "E-Mail bereits registriert.",
            },
            status_code=400,
        )

    # direkt einloggen: user_id in Session setzen
    request.session["user_id"] = user.id
    return RedirectResponse(
        url="/", status_code=303
    )  # 303 = see other (Form-POST -> GET)


@router.get("/signin")  # Signin-Form anzeigen
async def signin_form(request: Request):
    token = issue_csrf_token(request)
    return templates.TemplateResponse(
        "auth/signin.html", {"request": request, "csrf_token": token, "error": None}
    )


@router.post("/signin")  # Signin absenden
async def signin_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
):
    # CSRF prüfen
    if not validate_csrf(request, csrf_token):
        token = issue_csrf_token(request)
        return templates.TemplateResponse(
            "auth/signin.html",
            {
                "request": request,
                "csrf_token": token,
                "error": "CSRF ungültig. Bitte erneut senden.",
            },
            status_code=400,
        )

    # User laden
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(password, user.hashed_password):
        token = issue_csrf_token(request)
        return templates.TemplateResponse(
            "auth/signin.html",
            {
                "request": request,
                "csrf_token": token,
                "error": "E-Mail oder Passwort falsch.",
            },
            status_code=400,
        )

    # Session setzen und weiterleiten
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=303)


@router.get("/signout")  # Abmelden (einfach per GET)
async def signout(request: Request):
    # Nutzer ausloggen: Schlüssel entfernen (oder gesamte Session leeren)
    request.session.pop("user_id", None)
    return RedirectResponse(url="/", status_code=303)


@router.get("/delete")  # show confirm form
async def delete_form(request: Request):
    user_id = request.session.get("user_id")  # check login
    if not user_id:
        return RedirectResponse(url="/auth/signin", status_code=303)
    token = issue_csrf_token(request)  # new CSRF for this form
    return templates.TemplateResponse(
        "auth/delete.html",
        {"request": request, "csrf_token": token, "error": None},
    )


@router.post("/delete")  # perform deletion
async def delete_submit(
    request: Request,
    password: str = Form(...),  # user re-enters password
    csrf_token: str = Form(...),  # CSRF hidden input
    session: Session = Depends(get_session),  # DB session for this request
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/auth/signin", status_code=303)

    # CSRF must match what we issued on GET
    if not validate_csrf(request, csrf_token):
        token = issue_csrf_token(request)
        return templates.TemplateResponse(
            "auth/delete.html",
            {
                "request": request,
                "csrf_token": token,
                "error": "CSRF ungültig. Bitte erneut senden.",
            },
            status_code=400,
        )

    # Load current user
    user = session.get(User, user_id)
    if not user:
        request.session.pop(
            "user_id", None
        )  # session said logged-in but no DB row → clean up
        return RedirectResponse(url="/auth/signin", status_code=303)

    # Verify password matches stored hash
    if not verify_password(password, user.hashed_password):
        token = issue_csrf_token(request)
        return templates.TemplateResponse(
            "auth/delete.html",
            {
                "request": request,
                "csrf_token": token,
                "error": "Passwort stimmt nicht.",
            },
            status_code=400,
        )

    # Delete user and commit
    session.delete(user)
    session.commit()

    # Log out and redirect home
    request.session.pop("user_id", None)
    return RedirectResponse(url="/", status_code=303)
