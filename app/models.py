# app/models.py
from datetime import datetime  # für Zeitstempel wie "created_at"
from datetime import date
from enum import Enum  # small enums for clarity
from typing import Optional  # nullable fields

from sqlmodel import (
    UniqueConstraint,  # um E-Mail eindeutig zu machen (kein Doppel-Account)
)
from sqlmodel import (  # SQLModel base + columns; SQLModel = ORM-Basisklasse, Field = Spalten-Definition
    Field,
    SQLModel,
)


class User(SQLModel, table=True):  # "table=True" = echte DB-Tabelle erzeugen
    id: int | None = (
        Field(  # Primärschlüssel (int), None beim Erstellen -> DB vergibt Wert
            default=None, primary_key=True
        )
    )
    email: str = Field(  # E-Mail als Textspalte, indexiert für schnellere Suche
        index=True
    )
    hashed_password: str  # gespeichertes Passwort-Hash (nie Klartext)
    created_at: datetime = Field(  # automatisch gesetzter Erstellungszeitpunkt (UTC)
        default_factory=datetime.utcnow
    )

    __table_args__ = (  # zusätzliche DB-Regeln:
        UniqueConstraint("email", name="uq_users_email"),  # E-Mail muss eindeutig sein
    )


class LineType(str, Enum):
    income = "income"  # stored as TEXT
    expense = "expense"


class Frequency(str, Enum):
    monthly = "monthly"
    one_time = "one_time"


class Budget(SQLModel, table=True):
    __tablename__ = "budget"
    id: int | None = Field(default=None, primary_key=True)  # PK
    user_id: int = Field(index=True, foreign_key="user.id")  # owner
    name: str = Field(default="Main")  # future-proof
    is_active: bool = Field(default=True)  # archive later


class BudgetLine(SQLModel, table=True):
    __tablename__ = "budget_line"
    id: int | None = Field(default=None, primary_key=True)
    budget_id: int = Field(index=True, foreign_key="budget.id")  # parent
    type: LineType = Field(index=True)  # income/expense
    category: str  # e.g., Salary, Food
    subcategory: Optional[str] = None  # optional refinement
    amount: float  # MVP: float (ok for school)
    currency: str = Field(default="EUR")  # multi-currency support

    frequency: Frequency = Field(index=True)  # monthly/one_time

    # Month without day → store as integer YYYYMM (easy sorting & filtering)
    start_ym: Optional[int] = Field(default=None, index=True)  # used if monthly
    end_ym: Optional[int] = Field(default=None, index=True)  # null = open-ended
    one_time_ym: Optional[int] = Field(default=None, index=True)  # used if one_time

    is_active: bool = Field(default=True)  # soft-disable lines


class FXRate(SQLModel, table=True):
    __tablename__ = "fx_rate"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")  # per-user rates
    code: str = Field(index=True)  # e.g., USD
    rate_to_base: float  # 1 unit code → EUR
    valid_ym: int = Field(index=True)  # month (YYYYMM)


class Transaction(SQLModel, table=True):
    """
    A single real-life entry of money moving in/out.
    We keep both: an exact date AND a YYYYMM integer for fast monthly rollups.
    """

    id: Optional[int] = Field(default=None, primary_key=True)

    # Link to the user's active budget (you already have 'one budget per user')
    budget_id: int = Field(foreign_key="budget.id", index=True)

    # Same shape as budget lines, so reporting is consistent
    type: "LineType"  # income | expense
    category: str
    subcategory: Optional[str] = None

    amount: float
    currency: str = "EUR"

    # Actual transaction date
    txn_date: date

    # Denormalized month for joins with budgets / charts: e.g., 202501 for Jan 2025
    ym: int = Field(index=True)

    # Optional notes
    notes: Optional[str] = None
