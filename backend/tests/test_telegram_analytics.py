from datetime import timedelta
from decimal import Decimal

from app.services.booking import today_local
from tests.conftest import PNG, guest_book, make_apartment, register

SECRET = {"X-Telegram-Bot-Api-Secret-Token": "dev-webhook-secret"}


def d(n):
    return today_local() + timedelta(days=n)


def link_telegram(client, headers, chat_id=111):
    code = client.post("/api/telegram/link-code", headers=headers).json()["code"]
    r = client.post("/api/telegram/webhook", headers=SECRET,
                    json={"message": {"text": f"/start {code}", "chat": {"id": chat_id}}})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=headers).json()["telegram_linked"] is True


def press(client, data, chat_id=111):
    return client.post("/api/telegram/webhook", headers=SECRET,
                       json={"callback_query": {"id": "cb", "from": {"id": chat_id}, "data": data}})


def test_confirm_from_telegram_is_idempotent(client):
    h = register(client)
    make_apartment(client, h)
    link_telegram(client, h)
    token = guest_book(client, d(3), d(5)).json()["token"]
    client.post(f"/api/public/b/{token}/receipt", files={"file": ("c.png", PNG, "image/png")})
    bid = client.get("/api/bookings", headers=h).json()[0]["id"]

    press(client, f"confirm:{bid}")
    press(client, f"confirm:{bid}")  # повторное нажатие
    detail = client.get(f"/api/bookings/{bid}", headers=h).json()
    assert detail["status"] == "confirmed"
    assert sum(1 for e in detail["events"] if e["to_status"] == "confirmed") == 1
    notes = client.get("/api/notifications", headers=h).json()
    assert {n["kind"] for n in notes} >= {"new_booking", "receipt"}


def test_telegram_foreign_booking_and_bad_secret(client):
    a = register(client, "azamat")
    b = register(client, "bakyt")
    make_apartment(client, a)
    link_telegram(client, b, chat_id=222)
    token = guest_book(client, d(3), d(5)).json()["token"]
    client.post(f"/api/public/b/{token}/receipt", files={"file": ("c.png", PNG, "image/png")})
    bid = client.get("/api/bookings", headers=a).json()[0]["id"]
    press(client, f"confirm:{bid}", chat_id=222)
    assert client.get(f"/api/bookings/{bid}", headers=a).json()["status"] == "awaiting_confirmation"
    r = client.post("/api/telegram/webhook", json={"callback_query": {"id": "x", "from": {"id": 1}, "data": "confirm:1"}})
    assert r.status_code == 403


def test_analytics_matches_manual_calculation(client):
    h = register(client)
    a1 = make_apartment(client, h, slug="flat-1")
    a2 = make_apartment(client, h, slug="flat-2", price_per_night="2000")
    # 3 ночи по 3000 в flat-1 (Lalafo), подтверждена
    t = guest_book(client, d(2), d(5)).json()["token"]
    client.post(f"/api/public/b/{t}/receipt", files={"file": ("c.png", PNG, "image/png")})
    bid = client.get("/api/bookings", headers=h).json()[0]["id"]
    client.post(f"/api/bookings/{bid}/confirm", headers=h)
    # ручная бронь 2 ночи по 2000 во flat-2
    client.post("/api/bookings", headers=h, json={"apartment_id": a2["id"], "check_in": str(d(3)),
                                                   "check_out": str(d(5)), "name": "Айбек", "phone": "+996777000111"})
    # неоплаченная — в выручку не идёт
    guest_book(client, d(8), d(9), phone="+996700000003")
    client.post("/api/expenses", headers=h, json={"apartment_id": a1["id"], "category": "cleaning",
                                                  "amount": "1500", "spent_on": str(d(5))})

    res = client.get("/api/analytics", headers=h, params={"date_from": str(d(1)), "date_to": str(d(10))}).json()
    t = res["totals"]
    assert Decimal(t["revenue"]) == Decimal("13000")
    assert Decimal(t["expenses"]) == Decimal("1500")
    assert Decimal(t["profit"]) == Decimal("11500")
    assert t["nights"] == 5
    assert t["occupancy_pct"] == 25.0  # 5 ночей из 2 квартир × 10 дней
    flat1 = next(r for r in res["apartments"] if r["apartment_id"] == a1["id"])
    assert Decimal(flat1["profit"]) == Decimal("7500")
    sources = {s["source"]: s for s in res["sources"]}
    assert Decimal(sources["lalafo"]["revenue"]) == Decimal("9000")
    assert Decimal(sources["manual"]["revenue"]) == Decimal("4000")

    csv_text = client.get("/api/export/bookings.csv", headers=h).text
    assert "Квартира у ЦУМа" in csv_text
