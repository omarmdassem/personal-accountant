# app/services/transactions.py
"""
Small service helpers for Transactions.

Why:
- Keep router code thin later.
- Centralize logic like auto-filling YYYYMM from txn_date.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, Union

from sqlmodel import Session

from app.models import LineType, Transaction
from app.period_ym import ym_from_date


def create_transaction(
    session: Session,
    *,
    budget_id: int,
    type: Union[LineType, str],
    category: str,
    subcategory: Optional[str] = None,
    amount: float,
    currency: str = "EUR",
    txn_date: date,
    notes: Optional[str] = None,
) -> Transaction:
    """
    Create a Transaction row and commit it.

    Plain words:
    - We accept either a LineType enum ('income'/'expense') OR a string.
    - We compute 'ym' (YYYYMM) from txn_date for fast monthly rollups.
    - We commit & refresh so the caller gets a real, persisted object with an id.
    """

    if isinstance(type, str):
        type = LineType(type)

    txn = Transaction(
        budget_id=budget_id,
        type=type,
        category=category,
        subcategory=subcategory or None,
        amount=float(amount),
        currency=currency or "EUR",
        txn_date=txn_date,
        ym=ym_from_date(txn_date),
        notes=notes,
    )
    session.add(txn)
    session.commit()
    session.refresh(txn)
    return txn
