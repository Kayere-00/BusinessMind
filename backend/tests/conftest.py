"""Test fixtures: isolated SQLite DB + temp storage per session."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# --- Environment must be set BEFORE any app module is imported -------------
_tmp = tempfile.mkdtemp(prefix="businessmind_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["STORAGE_DIR"] = f"{_tmp}/storage"
os.environ["JWT_SECRET"] = "test-secret-key-not-for-production"
os.environ["OLLAMA_ENABLED"] = "false"
os.environ["ENV"] = "test"
os.environ["BCRYPT_ROUNDS"] = "4"          # fast hashing for tests
os.environ["AUTH_RATE_LIMIT"] = "1000"     # disabled except in the rate-limit test

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from scripts.generate_sample import generate  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


_counter = {"n": 0}


def register_org(client: TestClient, org: str | None = None) -> dict:
    """Register a fresh organization and return tokens + user info."""
    _counter["n"] += 1
    n = _counter["n"]
    org = org or f"Org-{n}"
    resp = client.post("/api/auth/register", json={
        "org_name": org,
        "full_name": f"Admin {n}",
        "email": f"admin{n}@example.com",
        "password": "Str0ngPassword!",
    })
    assert resp.status_code == 201, resp.text
    tokens = resp.json()
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200, me.text
    return {**tokens, "user": me.json()}


def auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture()
def sample_csv(tmp_path) -> Path:
    return generate(tmp_path / "sample.csv", rows=800)


def upload_sample(client: TestClient, tokens: dict, path: Path, name: str = "Sales 2024-2025") -> dict:
    with open(path, "rb") as f:
        resp = client.post(
            "/api/datasets",
            params={"name": name},
            files={"file": ("sample.csv", f, "text/csv")},
            headers=auth_headers(tokens),
        )
    assert resp.status_code == 201, resp.text
    return resp.json()
