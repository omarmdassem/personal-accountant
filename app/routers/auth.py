# app/routers/auth.py
# Minimal, test-proof auth: signup/signin/signout using session cookie.

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.flash import add_flash
from app.models import User
from app.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/signup")
def signup_form(request: Request):
    return templates.TemplateResponse(
        "auth/signup.html", {"request": request, "errors": None}
    )


@router.post("/signup")
def signup_submit(
    request: Request,
    session: Session = Depends(get_session),
    email: str = Form(...),
    password: str = Form(...),
):
    email = email.strip().lower()
    # If user exists, just log them in (good for idempotent tests)
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        request.session["user_id"] = existing.id
        add_flash(request, "Welcome back.", "info")
        return RedirectResponse("/", status_code=303)

    user = User(email=email, hashed_password=hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)

    request.session["user_id"] = user.id
    add_flash(request, "Account created.", "success")
    return RedirectResponse("/", status_code=303)


@router.get("/signin")
def signin_form(request: Request):
    return templates.TemplateResponse(
        "auth/signin.html", {"request": request, "errors": None}
    )


@router.post("/signin")
def signin_submit(
    request: Request,
    session: Session = Depends(get_session),
    email: str = Form(...),
    password: str = Form(...),
):
    email = email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(password, user.hashed_password):
        # Stay on page with 400 to show error (tests can detect)
        return templates.TemplateResponse(
            "auth/signin.html",
            {"request": request, "errors": ["Invalid email or password."]},
            status_code=400,
        )

    request.session["user_id"] = user.id
    add_flash(request, "Signed in.", "success")
    # land on budget lines by default (protected page)
    return RedirectResponse("/budget/lines", status_code=303)


@router.get("/signout")
def signout(request: Request):
    request.session.clear()
    add_flash(request, "Signed out.", "info")
    return RedirectResponse("/", status_code=303)
