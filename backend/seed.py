"""Демо-данные: владелец azamat / password123, менеджер aigul / password123, 3 квартиры и брони.

Запуск: python seed.py  (база должна быть пустой)
"""
from datetime import timedelta
from decimal import Decimal

from app.db import SessionLocal, init_db
from app.models import Account, Apartment, Role, User
from app.security import hash_password
from app.services import booking as svc

init_db()
with SessionLocal() as db:
    acc = Account(slug="azamat", name="Квартиры Азамата",
                  payment_details="MBank: +996 555 000 000 (Азамат Т.)")
    db.add_all([
        acc,
        User(account=acc, email="azamat@konok.kg", password_hash=hash_password("password123"),
             name="Азамат", role=Role.OWNER.value),
        User(account=acc, email="aigul@konok.kg", password_hash=hash_password("password123"),
             name="Айгуль", role=Role.MANAGER.value),
    ])
    db.flush()
    flats = [
        Apartment(account_id=acc.id, slug="tsum-2k", title="2-комнатная у ЦУМа", district="Центр",
                  address="ул. Киевская, 100, кв. 12", price_per_night=Decimal("3500"),
                  weekend_price=Decimal("4000"), max_guests=4, deposit=Decimal("3000"),
                  amenities=["Wi-Fi", "Стиральная машина", "Кондиционер"], description="Светлая квартира в центре."),
        Apartment(account_id=acc.id, slug="asanbai-studio", title="Студия в Асанбае", district="Асанбай",
                  address="мкр. Асанбай, 45, кв. 7", price_per_night=Decimal("2200"), max_guests=2,
                  deposit=Decimal("2000"), amenities=["Wi-Fi", "Парковка"]),
        Apartment(account_id=acc.id, slug="vostok-5", title="1-комнатная Восток-5", district="Восток-5",
                  address="мкр. Восток-5, 12, кв. 40", price_per_night=Decimal("1800"), max_guests=3,
                  amenities=["Wi-Fi"]),
    ]
    db.add_all(flats)
    db.flush()
    t = svc.today_local()
    svc.create_manual_booking(db, flats[0], name="Тимур Асанов", phone="+996555111222", check_in=t + timedelta(1),
                              check_out=t + timedelta(4), guests_count=2, status="confirmed", total_price=None,
                              actor="seed")
    svc.create_guest_booking(db, flats[1], name="Мария Ким", phone="+996700333444", check_in=t + timedelta(2),
                             check_out=t + timedelta(5), guests_count=1, source="instagram")
    svc.create_block(db, flats[2], check_in=t + timedelta(3), check_out=t + timedelta(6), reason="Ремонт ванной",
                     actor="seed")
    db.commit()
print("Готово: azamat@konok.kg / password123, витрина /azamat")
