# app/routers/budget.py
# Purpose: List and create planned budget lines for the current user.
# Minimal, page-based flow (no HTMX yet). Redirects to signin if user not logged in.

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session  # DB session per request
from app.models import Budget, BudgetLine, Frequency, LineType
from app.period_ym import format_ym, parse_mm_yy, validate_line_frequency_fields

router = APIRouter(prefix="/budget", tags=["budget"])
templates = Jinja2Templates(
    directory="app/templates"
)  # looks for templates in this folder


def _require_user_id(request: Request) -> int:
    """
    Read the logged-in user_id from the session.
    If missing, raise a redirect (303) to the signin page.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        # 303 redirect to signin keeps method safe for GET/POST
        raise HTTPException(status_code=303, headers={"Location": "/auth/signin"})
    return int(user_id)


def _get_line_for_user(
    session: Session, user_id: int, line_id: int
) -> BudgetLine | None:
    """
    Return the line only if it belongs to the current user's budget.
    """
    stmt = (
        select(BudgetLine)
        .join(Budget, BudgetLine.budget_id == Budget.id)
        .where(BudgetLine.id == line_id, Budget.user_id == user_id)
    )
    return session.exec(stmt).first()


def _get_or_create_budget(session: Session, user_id: int) -> Budget:
    """
    Return the active budget for this user. Create one if missing.
    Keeps 'one budget per user' simple for the MVP.
    """
    stmt = select(Budget).where(Budget.user_id == user_id, Budget.is_active)
    bud = session.exec(stmt).first()
    if bud:
        return bud
    bud = Budget(user_id=user_id, name="Main", is_active=True)
    session.add(bud)
    session.commit()
    session.refresh(bud)
    return bud


@router.get("/lines")
def list_lines(request: Request, session: Session = Depends(get_session)):
    """
    Render a table of budget lines for the current user.
    """
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        # Turn dependency-style redirect into a real response
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    budget = _get_or_create_budget(session, user_id)
    stmt = (
        select(BudgetLine)
        .where(BudgetLine.budget_id == budget.id)
        .order_by(BudgetLine.type, BudgetLine.category)
    )
    lines = session.exec(stmt).all()
    return templates.TemplateResponse(
        "budget/lines_list.html",
        {"request": request, "lines": lines},
    )


@router.get("/lines/new")
def new_line_form(request: Request):
    """
    Show empty form to create a new budget line.
    """
    try:
        _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    return templates.TemplateResponse(
        "budget/line_form.html",
        {"request": request, "errors": None},
    )


@router.post("/lines/new")
def create_line(
    request: Request,
    session: Session = Depends(get_session),
    # ----- form fields -----
    type: str = Form(...),  # "income" | "expense"
    category: str = Form(...),
    subcategory: str = Form(None),
    amount: float = Form(...),
    currency: str = Form("EUR"),
    frequency: str = Form(...),  # "monthly" | "one_time"
    start_mm_yy: str | None = Form(None),
    end_mm_yy: str | None = Form(None),
    one_time_mm_yy: str | None = Form(None),
):
    """
    Handle form submit, validate MM/YY logic, save, and redirect to list.
    """
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    budget = _get_or_create_budget(session, user_id)

    # Parse months according to frequency; reject invalid combos
    try:
        start_ym = (
            parse_mm_yy(start_mm_yy)
            if (frequency == "monthly" and start_mm_yy)
            else None
        )
        end_ym = (
            parse_mm_yy(end_mm_yy) if (frequency == "monthly" and end_mm_yy) else None
        )
        one_time_ym = (
            parse_mm_yy(one_time_mm_yy)
            if (frequency == "one_time" and one_time_mm_yy)
            else None
        )

        validate_line_frequency_fields(
            frequency=frequency,
            start_ym=start_ym,
            end_ym=end_ym,
            one_time_ym=one_time_ym,
        )
    except Exception as ex:
        # Re-render form with a simple error list
        return templates.TemplateResponse(
            "budget/line_form.html",
            {
                "request": request,
                "errors": [str(ex)],
                # (optional) could echo back fields, keeping MVP simple for now
            },
            status_code=400,
        )

    # Map strings to enums; FastAPI would also coerce via Pydantic model, but we keep it minimal here
    line = BudgetLine(
        budget_id=budget.id,
        type=LineType(type),
        category=category.strip(),
        subcategory=(subcategory.strip() if subcategory else None),
        amount=amount,
        currency=currency.strip() or "EUR",
        frequency=Frequency(frequency),
        start_ym=start_ym,
        end_ym=end_ym,
        one_time_ym=one_time_ym,
        is_active=True,
    )

    session.add(line)
    session.commit()
    # PRG pattern: redirect after POST
    return RedirectResponse(url="/budget/lines", status_code=303)


@router.get("/lines/{line_id}/edit")
def edit_line_form(
    line_id: int, request: Request, session: Session = Depends(get_session)
):
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    line = _get_line_for_user(session, user_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    # Pre-format months to MM/YY for the form
    start_mm_yy = format_ym(line.start_ym) if line.start_ym else ""
    end_mm_yy = format_ym(line.end_ym) if line.end_ym else ""
    one_time_mm_yy = format_ym(line.one_time_ym) if line.one_time_ym else ""

    return templates.TemplateResponse(
        "budget/line_form.html",
        {
            "request": request,
            "errors": None,
            "line": line,
            "start_mm_yy": start_mm_yy,
            "end_mm_yy": end_mm_yy,
            "one_time_mm_yy": one_time_mm_yy,
        },
    )


@router.post("/lines/{line_id}/edit")
def edit_line_submit(
    line_id: int,
    request: Request,
    session: Session = Depends(get_session),
    type: str = Form(...),
    category: str = Form(...),
    subcategory: str | None = Form(None),
    amount: float = Form(...),
    currency: str = Form("EUR"),
    frequency: str = Form(...),
    start_mm_yy: str | None = Form(None),
    end_mm_yy: str | None = Form(None),
    one_time_mm_yy: str | None = Form(None),
):
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    line = _get_line_for_user(session, user_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    try:
        start_ym = (
            parse_mm_yy(start_mm_yy)
            if (frequency == "monthly" and start_mm_yy)
            else None
        )
        end_ym = (
            parse_mm_yy(end_mm_yy) if (frequency == "monthly" and end_mm_yy) else None
        )
        one_time_ym = (
            parse_mm_yy(one_time_mm_yy)
            if (frequency == "one_time" and one_time_mm_yy)
            else None
        )
        validate_line_frequency_fields(
            frequency=frequency,
            start_ym=start_ym,
            end_ym=end_ym,
            one_time_ym=one_time_ym,
        )
    except Exception as ex:
        return templates.TemplateResponse(
            "budget/line_form.html",
            {
                "request": request,
                "errors": [str(ex)],
                "line": line,
                "start_mm_yy": start_mm_yy or "",
                "end_mm_yy": end_mm_yy or "",
                "one_time_mm_yy": one_time_mm_yy or "",
            },
            status_code=400,
        )

    # Apply changes
    line.type = LineType(type)
    line.category = category.strip()
    line.subcategory = subcategory.strip() if subcategory else None
    line.amount = amount
    line.currency = currency.strip() or "EUR"
    line.frequency = Frequency(frequency)
    line.start_ym = start_ym
    line.end_ym = end_ym
    line.one_time_ym = one_time_ym

    session.add(line)
    session.commit()
    return RedirectResponse("/budget/lines", status_code=303)


@router.post("/lines/{line_id}/delete")
def delete_line(
    line_id: int, request: Request, session: Session = Depends(get_session)
):
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    line = _get_line_for_user(session, user_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    session.delete(line)
    session.commit()
    return RedirectResponse("/budget/lines", status_code=303)
