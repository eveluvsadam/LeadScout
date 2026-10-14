"""Every test runs against a throwaway SQLite file and never touches the network."""
import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="leadscout-test-")
os.environ.update(
    DB_PATH=os.path.join(_tmp, "test.db"),
    DATABASE_URL="",
    APP_PASSWORD="",
    SELLER_EMAIL="",
    SELLER_EMAIL_APP_PASSWORD="",
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def lead():
    from app import database as db
    db.insert_lead({
        "name": "Test Bakery", "category": "Bakeries", "phone": "555-0100",
        "email": "owner@example.com", "website": None, "city": "Montpelier",
        "state": "Vermont", "country": "USA", "opportunity": "High",
    })
    return db.query_leads(limit=1)[0]
