# app/routers/transactions_import.py
from __future__ import annotations

import csv
import io
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.flash import add_flash
from app.models import Budget, LineType
from app.services.transactions import create_transaction

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/transactions/import", tags=["transactions-import"])


# ---- local helpers (avoid cross-imports) -----------------------------------


def _require_user_id(request: Request) -> int:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=303,
            headers={"Location": "/auth/signin"},
        )
    return int(user_id)


def _get_or_create_budget(session: Session, user_id: int) -> Budget:
    stmt = select(Budget).where(Budget.user_id == user_id, Budget.is_active)
    bud = session.exec(stmt).first()
    if bud:
        return bud
    bud = Budget(user_id=user_id, base_currency="EUR", is_active=True)
    session.add(bud)
    session.commit()
    session.refresh(bud)
    return bud


EXPECTED_HEADER = [
    "date",  # YYYY-MM-DD
    "type",  # income|expense
    "category",
    "subcategory",
    "amount",  # number
    "currency",  # e.g. EUR
    "notes",
]


@router.get("")
def import_form(request: Request):
    # If not signed in, redirect
    try:
        _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    return templates.TemplateResponse(
        "transactions/import.html",
        {
            "request": request,
            "errors": None,
        },
    )


@router.get("/template", response_class=PlainTextResponse)
def download_template():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(EXPECTED_HEADER)
    # one example row each
    w.writerow(["2025-01-01", "income", "Salary", "", "1000", "EUR", "January salary"])
    w.writerow(
        ["2025-01-15", "expense", "Groceries", "", "45.30", "EUR", "Weekly shop"]
    )
    return buf.getvalue()


@router.post("")
async def import_submit(
    request: Request,
    session: Session = Depends(get_session),
    file: UploadFile = File(...),
):
    # Redirect if not signed in
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    # Read whole file as text
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except Exception:
        return templates.TemplateResponse(
            "transactions/import.html",
            {
                "request": request,
                "errors": ["File must be UTF-8 text (CSV)."],
            },
            status_code=400,
        )

    # Parse CSV
    buf = io.StringIO(text)
    reader = csv.reader(buf)

    try:
        header = next(reader)
    except StopIteration:
        return templates.TemplateResponse(
            "transactions/import.html",
            {
                "request": request,
                "errors": ["CSV appears to be empty."],
            },
            status_code=400,
        )

    if header != EXPECTED_HEADER:
        return templates.TemplateResponse(
            "transactions/import.html",
            {
                "request": request,
                "errors": [
                    "Header mismatch. Download the template and use those exact "
                    "column names and order."
                ],
            },
            status_code=400,
        )

    # Validate + import rows
    budget = _get_or_create_budget(session, user_id)

    errors: List[str] = []
    imported = 0
    row_idx = 1  # data rows start at 1 (after header)
    for row in reader:
        row_idx += 1
        # Allow shorter rows (empty trailing columns)
        row = (row + [""] * len(EXPECTED_HEADER))[: len(EXPECTED_HEADER)]
        (
            s_date,
            s_type,
            s_cat,
            s_sub,
            s_amount,
            s_currency,
            s_notes,
        ) = [c.strip() for c in row]

        # Validate each field with clear messages
        try:
            if not s_date:
                raise ValueError("date is required (YYYY-MM-DD)")
            try:
                txn_dt = date.fromisoformat(s_date)
            except Exception:
                raise ValueError("date must be in YYYY-MM-DD format")

            s_type_l = s_type.lower()
            if s_type_l not in ("income", "expense"):
                raise ValueError("type must be 'income' or 'expense'")

            if not s_cat:
                raise ValueError("category is required")

            if not s_amount:
                raise ValueError("amount is required")
            try:
                amount = float(s_amount)
            except Exception:
                raise ValueError("amount must be a number")

            currency = s_currency or "EUR"

            # Create row
            create_transaction(
                session,
                budget_id=budget.id,
                type=LineType(s_type_l),
                category=s_cat,
                subcategory=(s_sub or None),
                amount=amount,
                currency=currency,
                txn_date=txn_dt,
                notes=(s_notes or None),
            )
            imported += 1

        except Exception as ex:  # collect row-level errors
            errors.append(f"Row {row_idx}: {ex}")

    if errors:
        # Show all errors and do not redirect
        return templates.TemplateResponse(
            "transactions/import.html",
            {
                "request": request,
                "errors": errors,
            },
            status_code=400,
        )

    add_flash(request, f"Imported {imported} transactions.", "success")
    return RedirectResponse("/transactions", status_code=303)
