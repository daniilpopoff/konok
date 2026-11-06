from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import update

from app.db import SessionLocal
from app.main import app
from app.models import Booking
from app.services.booking import expire_stale, today_local
from tests.conftest import PNG, guest_book, make_apartment, register


def d(days: int) -> date:
    return today_local() + timedelta(days=days)


def upload_receipt(client, token, content=PNG, name="check.png"):
    return client.post(f"/api/public/b/{token}/receipt", files={"file": (name, content, "image/png")})


# ---------- сквозной сценарий (ТЗ 6.2) ----------
def test_full_guest_flow(client):
    h = register(client)
    make_apartment(client, h)

    r = guest_book(client, d(10), d(13))
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "awaiting_payment"
    assert Decimal(b["total_price"]) == Decimal("9000")
    assert b["address"] is None, "адрес не показываем до подтверждения"
    token = b["token"]

    assert upload_receipt(client, token).json()["status"] == "awaiting_confirmation"

    bid = client.get("/api/bookings", headers=h).json()[0]["id"]
    assert client.post(f"/api/bookings/{bid}/confirm", headers=h).json()["status"] == "confirmed"

    page = client.get(f"/api/public/b/{token}").json()
    assert page["address"] == "ул. Киевская, 1, кв. 5"
    assert page["checkin_instructions"] == "Ключ у консьержа"

    r = client.post(f"/api/bookings/{bid}/check-in", json={"balance_paid": True, "deposit_received": True}, headers=h)
    assert r.json()["deposit_status"] == "received"
    client.post(f"/api/bookings/{bid}/check-out", headers=h)

    # закрыть нельзя, пока залог не закрыт
    assert client.post(f"/api/bookings/{bid}/close", headers=h).status_code == 409
    r = client.post(f"/api/bookings/{bid}/deposit", headers=h,
                    json={"action": "withheld", "withheld_amount": "500", "note": "Разбитая кружка"})
    assert r.json()["deposit_status"] == "withheld"
    assert client.post(f"/api/bookings/{bid}/close", headers=h).json()["status"] == "closed"

    assert client.post(f"/api/public/b/{token}/review", json={"rating": 5, "text": "Чисто, уютно"}).status_code == 201
    assert client.post(f"/api/public/b/{token}/review", json={"rating": 1}).status_code == 409

    apt = client.get("/api/public/azamat/flat-1").json()
    assert apt["rating"] == 5.0 and apt["reviews"][0]["guest_name"] == "Тимур"

    events = client.get(f"/api/bookings/{bid}", headers=h).json()["events"]
    assert [e["to_status"] for e in events][:3] == ["awaiting_payment", "awaiting_confirmation", "confirmed"]


# ---------- двойная бронь (ТЗ 6.1, табл. 6.1) ----------
def test_fifty_parallel_bookings_only_one_wins(client):
    h = register(client)
    make_apartment(client, h)

    def attempt(i: int) -> int:
        with TestClient(app) as c:
            return guest_book(c, d(20), d(22), phone=f"+99655500{i:04d}").status_code

    with ThreadPoolExecutor(max_workers=25) as pool:
        codes = list(pool.map(attempt, range(50)))
    assert codes.count(201) == 1, codes
    assert codes.count(409) == 49


def test_back_to_back_stays_allowed_overlap_rejected(client):
    h = register(client)
    make_apartment(client, h)
    assert guest_book(client, d(5), d(7)).status_code == 201
    assert guest_book(client, d(7), d(9), phone="+996700000001").status_code == 201  # выезд 12:00, заезд 14:00
    assert guest_book(client, d(8), d(10), phone="+996700000002").status_code == 409


def test_block_dates_prevents_booking(client):
    h = register(client)
    apt = make_apartment(client, h)
    r = client.post("/api/bookings/blocks", headers=h,
                    json={"apartment_id": apt["id"], "check_in": str(d(3)), "check_out": str(d(6)), "reason": "Ремонт"})
    assert r.status_code == 201
    assert guest_book(client, d(4), d(5)).status_code == 409


# ---------- удержание дат и истечение ----------
def test_unpaid_booking_expires_and_frees_dates(client):
    h = register(client)
    make_apartment(client, h)
    token = guest_book(client, d(4), d(6)).json()["token"]
    with SessionLocal() as db:
        db.execute(update(Booking).values(hold_expires_at=Booking.created_at - timedelta(minutes=1)))
        db.commit()
        assert expire_stale(db) == 1
        db.commit()
    assert client.get(f"/api/public/b/{token}").json()["status"] == "expired"
    assert upload_receipt(client, token).status_code == 409
    assert guest_book(client, d(4), d(6), phone="+996700111222").status_code == 201


def test_receipt_after_hold_passed_is_refused_with_410(client):
    h = register(client)
    make_apartment(client, h)
    token = guest_book(client, d(4), d(6)).json()["token"]
    with SessionLocal() as db:
        db.execute(update(Booking).values(hold_expires_at=Booking.created_at - timedelta(minutes=1)))
        db.commit()
    assert upload_receipt(client, token).status_code == 410
    assert client.get(f"/api/public/b/{token}").json()["status"] == "expired"


def test_reject_returns_to_payment_with_reason(client):
    h = register(client)
    make_apartment(client, h)
    token = guest_book(client, d(4), d(6)).json()["token"]
    upload_receipt(client, token)
    bid = client.get("/api/bookings", headers=h).json()[0]["id"]
    r = client.post(f"/api/bookings/{bid}/reject", json={"reason": "Сумма не совпадает"}, headers=h)
    assert r.json()["status"] == "awaiting_payment"
    page = client.get(f"/api/public/b/{token}").json()
    assert page["reject_reason"] == "Сумма не совпадает" and page["hold_expires_at"] is not None
    assert upload_receipt(client, token).json()["status"] == "awaiting_confirmation"


def test_invalid_transition_rejected(client):
    h = register(client)
    make_apartment(client, h)
    guest_book(client, d(4), d(6))
    bid = client.get("/api/bookings", headers=h).json()[0]["id"]
    r = client.post(f"/api/bookings/{bid}/check-in", json={}, headers=h)
    assert r.status_code == 409


# ---------- цена ----------
def test_quote_weekend_and_special_price(client):
    h = register(client)
    apt = make_apartment(client, h, weekend_price="4000")
    start = d(7)
    while start.weekday() != 3:  # ближайший четверг
        start += timedelta(days=1)
    client.put(f"/api/apartments/{apt['id']}/prices", json={"night": str(start), "price": "5000"}, headers=h)
    q = client.post("/api/public/azamat/flat-1/quote",
                    json={"check_in": str(start), "check_out": str(start + timedelta(days=4))}).json()
    # чт=5000 (особая), пт=4000, сб=4000, вс=3000
    assert [x["price"] for x in q["breakdown"]] == ["5000.00", "4000.00", "4000.00", "3000.00"]
    assert Decimal(q["total"]) == Decimal("16000")


def test_min_nights_and_past_dates(client):
    h = register(client)
    make_apartment(client, h, min_nights=2)
    assert guest_book(client, d(3), d(4)).status_code == 422
    assert guest_book(client, d(-2), d(1)).status_code == 422


# ---------- отмена ----------
def test_cancel_refund_rules(client):
    h = register(client)
    make_apartment(client, h, free_cancel_days=3)
    far = guest_book(client, d(30), d(32)).json()["token"]
    near = guest_book(client, d(1), d(3), phone="+996700000009").json()["token"]
    for t in (far, near):
        upload_receipt(client, t)
    assert client.post(f"/api/public/b/{far}/cancel", json={"reason": "Планы изменились"}).status_code == 200
    assert client.post(f"/api/public/b/{near}/cancel", json={}).status_code == 200
    rows = {b["start_at"][:10]: b for b in client.get("/api/bookings", headers=h).json()}
    assert rows[str(d(30))]["refund_due"] is True
    assert rows[str(d(1))]["refund_due"] is False
    # даты отменённой брони снова свободны
    assert guest_book(client, d(30), d(32), phone="+996700000010").status_code == 201


# ---------- файлы ----------
def test_fake_png_rejected(client):
    h = register(client)
    make_apartment(client, h)
    token = guest_book(client, d(4), d(6)).json()["token"]
    assert upload_receipt(client, token, content=b"<script>alert(1)</script>").status_code == 422


def test_consent_required(client):
    h = register(client)
    make_apartment(client, h)
    assert guest_book(client, d(4), d(6), consent=False).status_code == 422
