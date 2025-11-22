# app/routers/transactions.py
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.flash import add_flash
from app.models import Budget, LineType, Transaction
from app.period_ym import ym_from_date
from app.services.transactions import create_transaction

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/transactions", tags=["transactions"])


def _require_user_id(request: Request) -> int:
    user_id = request.session.get("user_id")
    if not user_id:
        # Redirect to signin if not logged in
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/auth/signin"}
        )
    return int(user_id)


def _get_or_create_budget(session: Session, user_id: int) -> Budget:
    # NOTE: pass the boolean column directly instead of '== True' to satisfy Ruff E712
    stmt = select(Budget).where(Budget.user_id == user_id, Budget.is_active)
    bud = session.exec(stmt).first()
    if bud:
        return bud
    bud = Budget(user_id=user_id, base_currency="EUR", is_active=True)
    session.add(bud)
    session.commit()
    session.refresh(bud)
    return bud


@router.get("")
def list_transactions(request: Request, session: Session = Depends(get_session)):
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    budget = _get_or_create_budget(session, user_id)
    txns = session.exec(
        select(Transaction)
        .where(Transaction.budget_id == budget.id)
        .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
    ).all()

    return templates.TemplateResponse(
        "transactions/list.html",
        {"request": request, "txns": txns, "budget": budget},
    )


@router.get("/new")
def new_form(request: Request, session: Session = Depends(get_session)):
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    budget = _get_or_create_budget(session, user_id)
    return templates.TemplateResponse(
        "transactions/form.html",
        {"request": request, "txn": None, "budget": budget, "errors": None},
    )


@router.post("/new")
async def create_submit(request: Request, session: Session = Depends(get_session)):
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    form = await request.form()
    try:
        ttype = (form.get("type") or "").strip().lower()
        category = (form.get("category") or "").strip()
        subcategory = (form.get("subcategory") or "").strip() or None
        amount = float(form.get("amount") or "0")
        currency = (form.get("currency") or "EUR").strip()
        txn_date_str = (form.get("txn_date") or "").strip()
        txn_dt = date.fromisoformat(txn_date_str)  # expects YYYY-MM-DD

        if ttype not in ("income", "expense"):
            raise ValueError("type must be income or expense")
        if not category:
            raise ValueError("category is required")
    except Exception as ex:
        return templates.TemplateResponse(
            "transactions/form.html",
            {"request": request, "txn": None, "budget": None, "errors": [str(ex)]},
            status_code=400,
        )

    budget = _get_or_create_budget(session, user_id)
    create_transaction(
        session,
        budget_id=budget.id,
        type=ttype,
        category=category,
        subcategory=subcategory,
        amount=amount,
        currency=currency,
        txn_date=txn_dt,
        notes=(form.get("notes") or None),
    )
    add_flash(request, "Transaction created.", "success")
    return RedirectResponse("/transactions", status_code=303)


@router.get("/{txn_id}/edit")
def edit_form(txn_id: int, request: Request, session: Session = Depends(get_session)):
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    budget = _get_or_create_budget(session, user_id)
    txn = session.get(Transaction, txn_id)
    if not txn or txn.budget_id != budget.id:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "transactions/form.html",
        {"request": request, "txn": txn, "budget": budget, "errors": None},
    )


@router.post("/{txn_id}/edit")
async def edit_submit(
    txn_id: int, request: Request, session: Session = Depends(get_session)
):
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    budget = _get_or_create_budget(session, user_id)
    txn = session.get(Transaction, txn_id)
    if not txn or txn.budget_id != budget.id:
        raise HTTPException(status_code=404)

    form = await request.form()
    try:
        ttype = (form.get("type") or "").strip().lower()
        txn.type = LineType(ttype)
        txn.category = (form.get("category") or "").strip()
        txn.subcategory = (form.get("subcategory") or "").strip() or None
        txn.amount = float(form.get("amount") or "0")
        txn.currency = (form.get("currency") or "EUR").strip()
        txn_date_str = (form.get("txn_date") or "").strip()
        txn.txn_date = date.fromisoformat(txn_date_str)
        txn.ym = ym_from_date(txn.txn_date)
        txn.notes = form.get("notes") or None

        if not txn.category:
            raise ValueError("category is required")
    except Exception as ex:
        return templates.TemplateResponse(
            "transactions/form.html",
            {"request": request, "txn": txn, "budget": budget, "errors": [str(ex)]},
            status_code=400,
        )

    session.add(txn)
    session.commit()
    add_flash(request, "Transaction updated.", "success")
    return RedirectResponse("/transactions", status_code=303)


@router.post("/{txn_id}/delete")
def delete_submit(
    txn_id: int, request: Request, session: Session = Depends(get_session)
):
    try:
        user_id = _require_user_id(request)
    except HTTPException as e:
        return RedirectResponse(e.headers["Location"], status_code=e.status_code)

    budget = _get_or_create_budget(session, user_id)
    txn = session.get(Transaction, txn_id)
    if txn and txn.budget_id == budget.id:
        session.delete(txn)
        session.commit()
        add_flash(request, "Transaction deleted.", "success")
    return RedirectResponse("/transactions", status_code=303)
