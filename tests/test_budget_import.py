import csv
import io

from fastapi.testclient import TestClient


def signup(client):
    client.post(
        "/auth/signup",
        data={"email": "t@test.com", "password": "pw"},
        follow_redirects=True,
    )


def _post_csv(client, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "type",
            "category",
            "subcategory",
            "amount",
            "currency",
            "frequency",
            "start_mm_yy",
            "end_mm_yy",
            "one_time_mm_yy",
        ]
    )
    for r in rows:
        w.writerow(r)
    buf.seek(0)
    files = {"file": ("import.csv", buf.getvalue(), "text/csv")}
    return client.post("/budget/lines/import", files=files, follow_redirects=False)


def test_import_happy_path(client: TestClient):
    signup(client)
    r = _post_csv(
        client,
        [
            ["income", "Salary", "", "1000", "EUR", "monthly", "01/25", "12/25", ""],
            ["income", "Bonus", "", "500", "EUR", "one_time", "", "", "06/25"],
        ],
    )
    assert r.status_code == 303
    html = client.get("/budget/lines").text
    assert "Salary" in html and "Bonus" in html


def test_import_bad_header(client: TestClient):
    signup(client)
    # Missing 'currency' column → simulate by changing header order/omitting in rows utility
    bad_csv = "type,category,amount,frequency\nexpense,Groceries,200,monthly\n"
    files = {"file": ("bad.csv", bad_csv, "text/csv")}
    r = client.post("/budget/lines/import", files=files, follow_redirects=False)
    assert r.status_code == 400
    assert "Header mismatch" in r.text


def test_import_validation_error(client: TestClient):
    signup(client)
    # monthly without start_mm_yy should error
    r = _post_csv(
        client,
        [
            ["expense", "Internet", "", "30", "EUR", "monthly", "", "", ""],
        ],
    )
    assert r.status_code == 400
    assert "Row" in r.text  # error list shown
