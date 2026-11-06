"""Права и изоляция данных (ТЗ 3.1, табл. 6.1 «Права и изоляция»)."""
from datetime import timedelta

from app.services.booking import today_local
from tests.conftest import PNG, guest_book, make_apartment, register


def d(n):
    return today_local() + timedelta(days=n)


def manager_headers(client, owner_h):
    client.post("/api/team/managers", headers=owner_h,
                json={"email": "aigul@test.kg", "password": "password123", "name": "Айгуль"})
    r = client.post("/api/auth/login", json={"email": "aigul@test.kg", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_owners_are_isolated(client):
    a = register(client, "azamat")
    b = register(client, "bakyt")
    apt = make_apartment(client, a)
    guest_book(client, d(3), d(5))
    bid = client.get("/api/bookings", headers=a).json()[0]["id"]

    assert client.get(f"/api/bookings/{bid}", headers=b).status_code == 404
    assert client.post(f"/api/bookings/{bid}/confirm", headers=b).status_code == 404
    assert client.get(f"/api/apartments/{apt['id']}", headers=b).status_code == 404
    assert client.get("/api/bookings", headers=b).json() == []
    assert client.get("/api/guests", headers=b).json() == []
    r = client.post("/api/bookings/blocks", headers=b,
                    json={"apartment_id": apt["id"], "check_in": str(d(10)), "check_out": str(d(11)), "reason": "x"})
    assert r.status_code == 404


def test_manager_cannot_see_finance_or_settings(client):
    owner = register(client)
    apt = make_apartment(client, owner)
    m = manager_headers(client, owner)
    assert client.get("/api/bookings", headers=m).status_code == 200
    assert client.get("/api/analytics", params={"date_from": str(d(0)), "date_to": str(d(30))},
                      headers=m).status_code == 403
    assert client.get("/api/expenses", headers=m).status_code == 403
    assert client.patch("/api/settings", json={"name": "x"}, headers=m).status_code == 403
    assert client.post("/api/apartments", json={"slug": "x2", "title": "x", "price_per_night": "1"},
                       headers=m).status_code == 403
    assert client.patch(f"/api/apartments/{apt['id']}", json={"price_per_night": "1"}, headers=m).status_code == 403


def test_receipt_not_public(client):
    owner = register(client)
    make_apartment(client, owner)
    token = guest_book(client, d(3), d(5)).json()["token"]
    client.post(f"/api/public/b/{token}/receipt", files={"file": ("c.png", PNG, "image/png")})
    bid = client.get("/api/bookings", headers=owner).json()[0]["id"]
    assert client.get(f"/api/bookings/{bid}/receipt").status_code == 401
    assert client.get(f"/api/bookings/{bid}/receipt", headers=owner).status_code == 200
    other = register(client, "bakyt")
    assert client.get(f"/api/bookings/{bid}/receipt", headers=other).status_code == 404


def test_slug_taken_and_reserved(client):
    register(client, "azamat")
    r = client.post("/api/auth/register", json={"email": "x@test.kg", "password": "password123", "name": "x",
                                                "business_name": "x", "slug": "azamat"})
    assert r.status_code == 409
    r = client.post("/api/auth/register", json={"email": "y@test.kg", "password": "password123", "name": "y",
                                                "business_name": "y", "slug": "admin"})
    assert r.status_code == 409


def test_blacklisted_guest_flagged_in_calendar(client):
    owner = register(client)
    make_apartment(client, owner)
    guest_book(client, d(3), d(5))
    gid = client.get("/api/guests", headers=owner).json()[0]["id"]
    client.patch(f"/api/guests/{gid}", json={"is_blacklisted": True, "blacklist_reason": "Шумная вечеринка"},
                 headers=owner)
    guest_book(client, d(10), d(12))  # тот же телефон
    cal = client.get("/api/bookings/calendar", params={"date_from": str(d(0)), "date_to": str(d(20))},
                     headers=owner).json()
    assert all(b["warning"] for b in cal["apartments"][0]["bookings"])
