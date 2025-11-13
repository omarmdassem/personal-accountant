# app/models.py
from datetime import datetime  # für Zeitstempel wie "created_at"

from sqlmodel import (
    UniqueConstraint,  # um E-Mail eindeutig zu machen (kein Doppel-Account)
)
from sqlmodel import (  # SQLModel = ORM-Basisklasse, Field = Spalten-Definition
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
