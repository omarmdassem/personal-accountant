# tests/test_transactions_service.py
"""
Unit tests for the transaction service helper (no HTTP).
We spin up a tiny SQLite DB, create tables, and verify behavior.
"""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, SQLModel, create_engine

from app.models import Budget, LineType, Transaction, User
from app.services.transactions import create_transaction


def _make_engine():
    # File DB in /tmp for visibility; could also use :memory:
    return create_engine("sqlite:///:memory:", echo=False)


def _bootstrap(engine):
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        # Minimal user & budget
        user = User(email="svc@test.com", hashed_password="x")
        s.add(user)
        s.commit()
        s.refresh(user)

        bud = Budget(user_id=user.id, base_currency="EUR", is_active=True)
        s.add(bud)
        s.commit()
        s.refresh(bud)
        return user, bud


def test_create_expense_autofills_ym():
    engine = _make_engine()
    user, bud = _bootstrap(engine)

    with Session(engine) as s:
        txn = create_transaction(
            s,
            budget_id=bud.id,
            type=LineType.expense,
            category="Groceries",
            amount=23.5,
            currency="EUR",
            txn_date=date(2025, 6, 15),
            notes="weekly shop",
        )

        assert txn.id is not None
        assert txn.ym == 202506
        assert txn.type == LineType.expense
        assert txn.category == "Groceries"
        # sanity: it exists in DB
        fetched = s.get(Transaction, txn.id)
        assert fetched is not None
        assert fetched.ym == 202506


def test_create_income_via_string_type():
    engine = _make_engine()
    user, bud = _bootstrap(engine)

    with Session(engine) as s:
        txn = create_transaction(
            s,
            budget_id=bud.id,
            type="income",  # string accepted
            category="Salary",
            amount=1000,
            currency="EUR",
            txn_date=date(2025, 1, 1),
        )
        assert txn.type == LineType.income
        assert txn.ym == 202501
