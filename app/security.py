# app/security.py
# Zweck: Helferfunktionen für Passwort-Hashing und CSRF-Token.

from hmac import compare_digest  # sicherer Vergleich (zeitkonstant)
from secrets import token_urlsafe  # erzeugt zufällige, schwer ratbare Tokens

from fastapi import Request  # Request, um auf die Session zuzugreifen
from passlib.context import (
    CryptContext,  # passlib kümmert sich um sicheres Hashing (bcrypt)
)

# Passwort-Hasher konfigurieren: wir benutzen "bcrypt"
pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")


def hash_password(plain: str) -> str:
    """
    Nimmt ein Klartext-Passwort und gibt einen sicheren Hash zurück.
    - Wenn du bcrypt später austauschen willst, änderst du nur die Config oben.
    - Änderungseffekt: bestehende Hashes bleiben gültig; neue werden mit neuem Schema erzeugt.
    """
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Prüft, ob 'plain' zum gespeicherten 'hashed' passt.
    - Gibt True/False zurück; wir speichern NIE das Klartext-Passwort.
    """
    return pwd_context.verify(plain, hashed)


# Schlüssel unter dem wir das CSRF-Token in der Session ablegen
CSRF_SESSION_KEY = "csrf_token"


def issue_csrf_token(request: Request) -> str:
    """
    Erzeugt ein zufälliges CSRF-Token, speichert es serverseitig in der Session
    und gibt es zurück, damit das Template es als hidden <input> einfügen kann.
    - Warum: Browser schickt das Token nur, wenn das echte Formular von uns stammt.
    - Wenn du den Key-Namen änderst, musst du auch die Form-Auswertung anpassen.
    """
    token = token_urlsafe(32)  # ~43 Zeichen, ausreichend stark
    request.session[CSRF_SESSION_KEY] = token
    return token


def validate_csrf(request: Request, token_from_form: str) -> bool:
    """
    Vergleicht das Token aus dem Formular mit dem in der Session.
    - compare_digest: sicherer Vergleich gegen Timing-Angriffe.
    - Rückgabe True = OK, False = blocken.
    - Tipp: Nach erfolgreichem POST kannst du das Token rotieren/neu ausgeben.
    """
    token_in_session = request.session.get(CSRF_SESSION_KEY)
    return bool(
        token_in_session
        and token_from_form
        and compare_digest(token_in_session, token_from_form)
    )
