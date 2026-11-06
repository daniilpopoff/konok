"""Демо-данные: владелец azamat / password123, менеджер aigul / password123, 3 квартиры и брони.

Запуск: python seed.py  (база должна быть пустой)
"""
from datetime import timedelta
from decimal import Decimal

from app.db import SessionLocal, init_db
import os

from app.config import settings
from app.models import Account, Apartment, DepositStatus, Expense, Review, Role, User
from app.security import hash_password
from app.services import booking as svc

init_db()
# Демо-чек (маленькая PNG-картинка), чтобы у брони «чек на проверке» был файл
_receipt = os.path.join(settings.media_dir, "private", "receipts", "demo.png")
os.makedirs(os.path.dirname(_receipt), exist_ok=True)
with open(_receipt, "wb") as fh:
    import base64
    fh.write(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="))

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
    # Чек на проверке — чтобы было что подтвердить
    pending, _ = svc.create_guest_booking(db, flats[0], name="Айбек Сыдыков", phone="+996777000111",
                                          check_in=t + timedelta(6), check_out=t + timedelta(8), guests_count=2,
                                          source="lalafo")
    svc.attach_receipt(db, pending, "private/receipts/demo.png")
    # Прошлые брони: заселились, выехали, оставили отзыв — для аналитики и отзывов
    past = [
        (flats[0], "Айжан Токтогулова", "+996555222333", -12, -9, Decimal("10500"), 5, "Чисто, тепло, всё как на фото."),
        (flats[1], "Нурлан Жумабаев", "+996555909090", -8, -4, Decimal("8800"), 4, "Удобно, но шумновато вечером."),
        (flats[2], "Жанна Бекова", "+996700121212", -6, -3, Decimal("5400"), 5, "Хозяин ответил за 5 минут!"),
    ]
    for flat, name, phone, a, b, total, rating, text in past:
        bk = svc.create_manual_booking(db, flat, name=name, phone=phone, check_in=t + timedelta(a),
                                       check_out=t + timedelta(b), guests_count=2, status="confirmed",
                                       total_price=total, actor="seed")
        bk.source = "lalafo" if rating == 5 else "instagram"
        svc.check_in(db, bk, balance_paid=True, deposit_received=True, actor="seed")
        svc.check_out(db, bk, actor="seed")
        if bk.deposit_status == DepositStatus.RECEIVED.value:
            svc.settle_deposit(db, bk, action="returned", withheld=Decimal("0"), note="", actor="seed")
        svc.close(db, bk, actor="seed")
        db.add(Review(booking_id=bk.id, apartment_id=flat.id, rating=rating, text=text))
    db.add_all([
        Expense(account_id=acc.id, apartment_id=flats[0].id, category="cleaning", amount=Decimal("1500"),
                spent_on=t - timedelta(9), note="Уборка после гостя"),
        Expense(account_id=acc.id, apartment_id=flats[1].id, category="utilities", amount=Decimal("2300"),
                spent_on=t - timedelta(5), note="Свет и газ"),
    ])
    db.commit()
print("Готово: azamat@konok.kg / password123, витрина /azamat")
