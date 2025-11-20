# tests/conftest.py
# Test setup: temporary SQLite DB and dependency override for sessions.

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

# Ensure repo root on sys.path so "import app" works
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.models as _models  # noqa: F401,E402  # registers tables on SQLModel.metadata
from app.db import get_session  # noqa: E402

# Import the FastAPI app with an alias (avoid name collision with package "app")
from app.main import app as fastapi_app  # noqa: E402


@pytest.fixture()
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_app.db"


@pytest.fixture()
def test_engine(tmp_db_path: Path):
    # File-based SQLite so multiple connections share the same DB
    url = f"sqlite:///{tmp_db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)  # tables from app.models
    try:
        yield engine
    finally:
        if tmp_db_path.exists():
            try:
                tmp_db_path.unlink()
            except Exception:
                pass


@pytest.fixture()
def client(test_engine):
    # Override the app's DB session to use our test engine
    def _get_test_session():
        with Session(test_engine) as s:
            yield s

    fastapi_app.dependency_overrides[get_session] = _get_test_session
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()
