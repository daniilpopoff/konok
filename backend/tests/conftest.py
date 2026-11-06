import os
import tempfile

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@/konok_test?host=/tmp")
os.environ["MEDIA_DIR"] = tempfile.mkdtemp(prefix="konok-media-")
os.environ["EXPIRE_INTERVAL_SECONDS"] = "3600"
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-1234567890")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import Base, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    init_db()
    yield


@pytest.fixture(autouse=True)
def _clean():
    yield
    names = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def register(client, slug="azamat", email=None):
    r = client.post("/api/auth/register", json={
        "email": email or f"{slug}@test.kg", "password": "password123", "name": slug.title(),
        "business_name": f"Квартиры {slug}", "slug": slug,
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make_apartment(client, headers, slug="flat-1", **extra):
    body = {"slug": slug, "title": "Квартира у ЦУМа", "district": "Центр", "address": "ул. Киевская, 1, кв. 5",
            "checkin_instructions": "Ключ у консьержа", "price_per_night": "3000", "prepayment": "1000",
            "deposit": "2000", "max_guests": 4, **extra}
    r = client.post("/api/apartments", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def guest_book(client, check_in, check_out, owner="azamat", flat="flat-1", phone="+996555123456", **extra):
    return client.post(f"/api/public/{owner}/{flat}/bookings", json={
        "check_in": str(check_in), "check_out": str(check_out), "guests_count": 2, "name": "Тимур Асанов",
        "phone": phone, "consent": True, "source": "lalafo", **extra})
