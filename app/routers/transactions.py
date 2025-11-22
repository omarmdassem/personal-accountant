# app/routers/transactions.py
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.config import get_settings
from app.db import get_session
from app.flash import add_flash
from app.models import Budget, Transaction
from app.period_ym import ym_from_date
from app.security import require_user_id

router = APIRouter(prefix="/transactions", tags=["transactions"])

settings = get_settings()


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


def _parse_date(s: str) -> date:
    try:
        y, m, d = (int(p) for p in s.split("-"))
        return date(y, m, d)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid date.") from exc


@router.get("", response_class=HTMLResponse)
def list_transactions(
    request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    user_id = require_user_id(request)
    bud = _get_or_create_budget(session, user_id)
    stmt = (
        select(Transaction)
        .where(Transaction.budget_id == bud.id)
        .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
    )
    rows = list(session.exec(stmt).all())
    return request.app.state.templates.TemplateResponse(
        "transactions/list.html",
        {"request": request, "rows": rows, "title": "Transactions"},
    )


@router.get("/new", response_class=HTMLResponse)
def new_transaction_form(
    request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    require_user_id(request)
    return request.app.state.templates.TemplateResponse(
        "transactions/form.html",
        {
            "request": request,
            "title": "New Transaction",
            "tx": None,
            "default_currency": settings.base_currency,
        },
    )


@router.post("/new")
def create_transaction(
    request: Request,
    session: Session = Depends(get_session),
    date: str = Form(...),
    type: str = Form(...),
    category: str = Form(...),
    subcategory: Optional[str] = Form(None),
    amount: float = Form(...),
    currency: str = Form(...),
    notes: Optional[str] = Form(None),
) -> RedirectResponse:
    user_id = require_user_id(request)
    bud = _get_or_create_budget(session, user_id)
    txn_date = _parse_date(date)
    tx = Transaction(
        budget_id=bud.id,
        type=type,
        category=category,
        subcategory=(subcategory or None),
        amount=amount,
        currency=currency,
        txn_date=txn_date,
        ym=ym_from_date(txn_date),
        notes=(notes or None),
    )
    session.add(tx)
    session.commit()
    add_flash(request, "success", "Transaction created.")
    return RedirectResponse("/transactions", status_code=303)


@router.get("/{tx_id}/edit", response_class=HTMLResponse)
def edit_transaction_form(
    tx_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    user_id = require_user_id(request)
    bud = _get_or_create_budget(session, user_id)
    tx = session.get(Transaction, tx_id)
    if not tx or tx.budget_id != bud.id:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return request.app.state.templates.TemplateResponse(
        "transactions/form.html",
        {
            "request": request,
            "title": "Edit Transaction",
            "tx": tx,
            "default_currency": settings.base_currency,
        },
    )


@router.post("/{tx_id}/edit")
def update_transaction(
    tx_id: int,
    request: Request,
    session: Session = Depends(get_session),
    date: str = Form(...),
    type: str = Form(...),
    category: str = Form(...),
    subcategory: Optional[str] = Form(None),
    amount: float = Form(...),
    currency: str = Form(...),
    notes: Optional[str] = Form(None),
) -> RedirectResponse:
    user_id = require_user_id(request)
    bud = _get_or_create_budget(session, user_id)
    tx = session.get(Transaction, tx_id)
    if not tx or tx.budget_id != bud.id:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    txn_date = _parse_date(date)
    tx.txn_date = txn_date
    tx.ym = ym_from_date(txn_date)
    tx.type = type
    tx.category = category
    tx.subcategory = subcategory or None
    tx.amount = amount
    tx.currency = currency
    tx.notes = notes or None

    session.add(tx)
    session.commit()
    add_flash(request, "success", "Transaction updated.")
    return RedirectResponse("/transactions", status_code=303)


@router.post("/{tx_id}/delete")
def delete_transaction(
    tx_id: int, request: Request, session: Session = Depends(get_session)
) -> RedirectResponse:
    user_id = require_user_id(request)
    bud = _get_or_create_budget(session, user_id)
    tx = session.get(Transaction, tx_id)
    if not tx or tx.budget_id != bud.id:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    session.delete(tx)
    session.commit()
    add_flash(request, "success", "Transaction deleted.")
    return RedirectResponse("/transactions", status_code=303)
