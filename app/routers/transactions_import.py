# app/routers/transactions_import.py
from __future__ import annotations

import csv
import io
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import (
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from sqlmodel import Session, select

from app.config import get_settings
from app.db import get_session
from app.flash import add_flash
from app.models import Budget, Transaction
from app.period_ym import ym_from_date
from app.security import require_user_id

router = APIRouter(prefix="/transactions", tags=["transactions"])
settings = get_settings()

TEMPLATE_COLUMNS = [
    "date",  # YYYY-MM-DD
    "type",  # income|expense
    "category",
    "subcategory",
    "amount",
    "currency",
    "notes",
]


def _get_or_create_budget(session: Session, user_id: int) -> Budget:
    stmt = select(Budget).where(Budget.user_id == user_id, Budget.is_active)
    bud = session.exec(stmt).first()
    if bud:
        return bud
    bud = Budget(user_id=user_id, base_currency=settings.base_currency, is_active=True)
    session.add(bud)
    session.commit()
    session.refresh(bud)
    return bud


def _parse_date_iso(s: str) -> date:
    # Expect ISO yyyy-mm-dd from the template
    try:
        y, m, d = (int(p) for p in s.strip().split("-"))
        return date(y, m, d)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Invalid date format, expected YYYY-MM-DD") from exc


@router.get("/template", response_class=PlainTextResponse)
def download_csv_template() -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(TEMPLATE_COLUMNS)
    # example row (users can delete it)
    w.writerow(["2025-01-15", "income", "Salary", "", "1000", "EUR", "January salary"])
    data = buf.getvalue()
    headers = {
        "Content-Disposition": 'attachment; filename="transactions_template.csv"',
        "Content-Type": "text/csv; charset=utf-8",
    }
    return Response(content=data, headers=headers, media_type="text/csv")


@router.get("/import", response_class=HTMLResponse)
def transactions_import_form(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    # auth check so the page is protected
    require_user_id(request)
    return request.app.state.templates.TemplateResponse(
        "transactions/import_form.html",
        {"request": request, "title": "Import Transactions"},
    )


@router.post("/import")
def transactions_import_upload(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    user_id = require_user_id(request)
    bud = _get_or_create_budget(session, user_id)

    # Read CSV as text (support utf-8-sig to drop BOM)
    raw = file.file.read()
    try:
        text = raw.decode("utf-8-sig")
    except Exception:
        text = raw.decode()  # fallback

    reader = csv.DictReader(io.StringIO(text))
    got = [c.strip() for c in (reader.fieldnames or [])]
    expected = TEMPLATE_COLUMNS

    if got != expected:
        return request.app.state.templates.TemplateResponse(
            "transactions/import_form.html",
            {
                "request": request,
                "title": "Import Transactions",
                "errors": [
                    "Header mismatch. Please download the template and use those exact column names.",
                    f"Expected: {', '.join(expected)}",
                    f"Got: {', '.join(got) if got else '(none)'}",
                ],
            },
            status_code=400,
        )

    errors: List[str] = []
    to_add: List[Transaction] = []

    for idx, row in enumerate(reader, start=2):  # start=2 because row 1 is header
        try:
            d = row["date"].strip()
            t = row["type"].strip().lower()
            cat = row["category"].strip()
            sub = (row["subcategory"] or "").strip() or None
            amount_str = row["amount"].strip()
            cur = row["currency"].strip().upper()
            notes = (row["notes"] or "").strip() or None

            if t not in {"income", "expense"}:
                raise ValueError("type must be 'income' or 'expense'")

            txn_date = _parse_date_iso(d)
            try:
                amount = float(amount_str)
            except Exception as exc:  # noqa: BLE001
                raise ValueError("amount must be a number") from exc

            tx = Transaction(
                budget_id=bud.id,
                type=t,
                category=cat,
                subcategory=sub,
                amount=amount,
                currency=cur,
                txn_date=txn_date,
                ym=ym_from_date(txn_date),
                notes=notes,
            )
            to_add.append(tx)

        except Exception as exc:  # noqa: BLE001
            errors.append(f"Row {idx}: {exc}")

    if errors:
        return request.app.state.templates.TemplateResponse(
            "transactions/import_form.html",
            {"request": request, "title": "Import Transactions", "errors": errors},
            status_code=400,
        )

    for tx in to_add:
        session.add(tx)
    session.commit()

    add_flash(request, "success", f"Imported {len(to_add)} transactions.")
    return RedirectResponse("/transactions", status_code=303)
