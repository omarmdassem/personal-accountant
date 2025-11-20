# app/routers/budget.py
# Purpose: Budget Lines CRUD (list/create/edit/delete) for the signed-in user.
# - Auto-creates a Budget for the user on first use.
# - Validates month-only fields via period helpers (MM/YY ↔ YYYYMM).
# - Uses flash messages to confirm actions after redirects.

import csv
import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.flash import add_flash
from app.models import Budget, BudgetLine, Frequency, LineType
from app.period_ym import format_ym, parse_mm_yy, validate_line_frequency_fields

router = APIRouter(prefix="/budget", tags=["budget"])
templates = Jinja2Templates(directory="app/templates")


def _require_user_id(request: Request) -> int:
    """
    Read logged-in user_id from the session.
    If missing (or SessionMiddleware not set), redirect to signin.
    """
    try:
        user_id = request.session.get("user_id")
    except AssertionError:
        raise HTTPException(status_code=303, headers={"Location": "/auth/signin"})
    if not user_id:
        raise HTTPException(status_code=303, headers={"Location": "/auth/signin"})
    return int(user_id)


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


def _get_line_for_user(
    session: Session, user_id: int, line_id: int
) -> BudgetLine | None:
    """
    Return the line only if it belongs to the current user's budget.
    Prevents editing/deleting others' data.
    """
    stmt = (
        select(BudgetLine)
        .join(Budget, BudgetLine.budget_id == Budget.id)
        .where(BudgetLine.id == line_id, Budget.user_id == user_id)
    )
    return session.exec(stmt).first()


@router.get("/lines")
def list_lines(request: Request, session: Session = Depends(get_session)):
    """Render a table of budget lines for the current user."""
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
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
    """Show empty form to create a new budget line."""
    try:
        _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    return templates.TemplateResponse(
        "budget/line_form.html",
        {"request": request, "errors": None, "line": None},
    )


@router.post("/lines/new")
def create_line(
    request: Request,
    session: Session = Depends(get_session),
    # ----- form fields -----
    type: str = Form(...),  # "income" | "expense"
    category: str = Form(...),
    subcategory: str | None = Form(None),
    amount: float = Form(...),
    currency: str = Form("EUR"),
    frequency: str = Form(...),  # "monthly" | "one_time"
    start_mm_yy: str | None = Form(None),
    end_mm_yy: str | None = Form(None),
    one_time_mm_yy: str | None = Form(None),
):
    """Handle create submit, validate, save, and redirect to list."""
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    budget = _get_or_create_budget(session, user_id)

    # Parse months according to frequency; reject invalid combos.
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
            {"request": request, "errors": [str(ex)], "line": None},
            status_code=400,
        )

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
    add_flash(request, "Budget line created.", "success")
    return RedirectResponse(url="/budget/lines", status_code=303)


@router.get("/lines/{line_id}/edit")
def edit_line_form(
    line_id: int, request: Request, session: Session = Depends(get_session)
):
    """Show prefilled edit form for an existing budget line."""
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    line = _get_line_for_user(session, user_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

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
    """Handle edit submit, validate, save, and redirect to list."""
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
    add_flash(request, "Budget line updated.", "success")
    return RedirectResponse("/budget/lines", status_code=303)


@router.post("/lines/{line_id}/delete")
def delete_line(
    line_id: int, request: Request, session: Session = Depends(get_session)
):
    """Delete a budget line that belongs to the current user."""
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    line = _get_line_for_user(session, user_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    session.delete(line)
    session.commit()
    add_flash(request, "Budget line deleted.", "success")
    return RedirectResponse("/budget/lines", status_code=303)


@router.get("/lines/template.csv")
def lines_template_csv():
    """
    Serve a minimal CSV template users can fill.
    Columns: type,category,subcategory,amount,currency,frequency,start_mm_yy,end_mm_yy,one_time_mm_yy
    """
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(
        [
            "type",
            "category",
            "subcategory",
            "amount",
            "currency",
            "frequency",
            "start_mm_yy",
            "end_mm_yy",
            "one_time_mm_yy",
        ]
    )
    # Example rows (one monthly, one one-time)
    w.writerow(["income", "Salary", "", "1000", "EUR", "monthly", "01/25", "12/25", ""])
    w.writerow(["income", "Bonus", "", "500", "EUR", "one_time", "", "", "06/25"])
    data = out.getvalue()
    return Response(
        content=data,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="budget_lines_template.csv"'
        },
    )


@router.get("/lines/import")
def lines_import_form(request: Request):
    try:
        _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    return templates.TemplateResponse(
        "budget/lines_import.html",
        {"request": request, "errors": None},
    )


@router.post("/lines/import")
async def lines_import_submit(
    request: Request,
    session: Session = Depends(get_session),
    file: UploadFile = File(...),
):
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    # Read file as UTF-8 text
    raw = await file.read()
    text = raw.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    required_cols = [
        "type",
        "category",
        "subcategory",
        "amount",
        "currency",
        "frequency",
        "start_mm_yy",
        "end_mm_yy",
        "one_time_mm_yy",
    ]
    if reader.fieldnames is None or any(
        c not in reader.fieldnames for c in required_cols
    ):
        return templates.TemplateResponse(
            "budget/lines_import.html",
            {
                "request": request,
                "errors": [
                    "Header mismatch. Please download the template and use those exact column names."
                ],
            },
            status_code=400,
        )

    budget = _get_or_create_budget(session, user_id)

    created = 0
    errors: list[str] = []
    for idx, row in enumerate(reader, start=2):  # start=2 because header is line 1
        try:
            t = (row["type"] or "").strip().lower()  # "income" | "expense"
            cat = (row["category"] or "").strip()
            sub = (row["subcategory"] or "").strip() or None
            amt = float(row["amount"]) if row["amount"] else None
            cur = (row["currency"] or "EUR").strip()
            freq = (row["frequency"] or "").strip().lower()  # "monthly" | "one_time"
            start_mm_yy = (row["start_mm_yy"] or "").strip()
            end_mm_yy = (row["end_mm_yy"] or "").strip()
            one_time_mm_yy = (row["one_time_mm_yy"] or "").strip()

            if not t or not cat or amt is None or not freq:
                raise ValueError("Missing one of: type, category, amount, frequency.")

            # Convert month fields
            start_ym = (
                parse_mm_yy(start_mm_yy)
                if (freq == "monthly" and start_mm_yy)
                else None
            )
            end_ym = (
                parse_mm_yy(end_mm_yy) if (freq == "monthly" and end_mm_yy) else None
            )
            one_time_ym = (
                parse_mm_yy(one_time_mm_yy)
                if (freq == "one_time" and one_time_mm_yy)
                else None
            )

            # Validate the combo logic
            validate_line_frequency_fields(
                frequency=freq,
                start_ym=start_ym,
                end_ym=end_ym,
                one_time_ym=one_time_ym,
            )

            # Create row
            line = BudgetLine(
                budget_id=budget.id,
                type=LineType(t),
                category=cat,
                subcategory=sub,
                amount=amt,
                currency=cur or "EUR",
                frequency=Frequency(freq),
                start_ym=start_ym,
                end_ym=end_ym,
                one_time_ym=one_time_ym,
                is_active=True,
            )
            session.add(line)
            created += 1
        except Exception as ex:
            errors.append(f"Row {idx}: {ex}")

    # Commit what we could save (simple MVP: partial success allowed)
    session.commit()

    if created:
        add_flash(request, f"Imported {created} line(s).", "success")
    if errors:
        # Show errors on the same page (400 so user sees issues)
        return templates.TemplateResponse(
            "budget/lines_import.html",
            {"request": request, "errors": errors},
            status_code=400,
        )

    return RedirectResponse("/budget/lines", status_code=303)
