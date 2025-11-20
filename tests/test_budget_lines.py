# tests/test_budget_lines.py
from sqlmodel import select

from app.db import get_session
from app.main import app as fastapi_app
from app.models import BudgetLine


def signup_and_signin(client, email="t@test.com", password="pw123456"):
    # Follow redirects so the session cookie gets set
    client.post(
        "/auth/signup",
        data={"email": email, "password": password},
        follow_redirects=True,
    )
    client.post(
        "/auth/signin",
        data={"email": email, "password": password},
        follow_redirects=True,
    )
    # Prove we are logged in: protected page should be 200 (not redirect)
    r = client.get("/budget/lines", follow_redirects=False)
    assert r.status_code == 200


def test_redirect_when_not_signed_in(client):
    r = client.get("/budget/lines", follow_redirects=False)
    assert r.status_code == 303
    assert "/auth/signin" in r.headers.get("Location", "")


def test_create_monthly_and_one_time_lines(client):
    signup_and_signin(client)

    r1 = client.post(
        "/budget/lines/new",
        data={
            "type": "income",
            "category": "Salary",
            "amount": "1000",
            "currency": "EUR",
            "frequency": "monthly",
            "start_mm_yy": "01/25",
            "end_mm_yy": "12/25",
        },
        follow_redirects=False,
    )
    assert r1.status_code == 303

    r2 = client.post(
        "/budget/lines/new",
        data={
            "type": "income",
            "category": "Bonus",
            "amount": "500",
            "currency": "EUR",
            "frequency": "one_time",
            "one_time_mm_yy": "06/25",
        },
        follow_redirects=False,
    )
    assert r2.status_code == 303

    html = client.get("/budget/lines").text
    assert "Salary" in html and "Bonus" in html


def test_validation_errors(client):
    signup_and_signin(client)

    # monthly but missing start_mm_yy → 400
    r_bad = client.post(
        "/budget/lines/new",
        data={
            "type": "expense",
            "category": "Groceries",
            "amount": "200",
            "currency": "EUR",
            "frequency": "monthly",
            "start_mm_yy": "",
        },
        follow_redirects=False,
    )
    assert r_bad.status_code == 400

    # one_time but missing date → 400
    r_bad2 = client.post(
        "/budget/lines/new",
        data={
            "type": "expense",
            "category": "Doctor",
            "amount": "80",
            "currency": "EUR",
            "frequency": "one_time",
        },
        follow_redirects=False,
    )
    assert r_bad2.status_code == 400


def _get_line_id_by_category(category: str):
    # Pull a session from the same override the app uses
    gen = fastapi_app.dependency_overrides[get_session]()
    with next(gen) as s:
        line = s.exec(select(BudgetLine).where(BudgetLine.category == category)).first()
        return line.id if line else None


def test_edit_and_delete(client):
    signup_and_signin(client)

    r_new = client.post(
        "/budget/lines/new",
        data={
            "type": "expense",
            "category": "Internet",
            "amount": "30",
            "currency": "EUR",
            "frequency": "monthly",
            "start_mm_yy": "01/25",
        },
        follow_redirects=False,
    )
    assert r_new.status_code == 303

    line_id = _get_line_id_by_category("Internet")
    assert line_id is not None

    r_edit = client.post(
        f"/budget/lines/{line_id}/edit",
        data={
            "type": "expense",
            "category": "Internet",
            "amount": "35",
            "currency": "EUR",
            "frequency": "monthly",
            "start_mm_yy": "01/25",
        },
        follow_redirects=False,
    )
    assert r_edit.status_code == 303

    # Confirm edit
    gen = fastapi_app.dependency_overrides[get_session]()
    with next(gen) as s:
        assert float(s.get(BudgetLine, line_id).amount) == 35.0

    # Delete
    r_del = client.post(f"/budget/lines/{line_id}/delete", follow_redirects=False)
    assert r_del.status_code == 303

    # Confirm gone
    gen = fastapi_app.dependency_overrides[get_session]()
    with next(gen) as s:
        assert s.get(BudgetLine, line_id) is None
