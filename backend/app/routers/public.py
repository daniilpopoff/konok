"""Публичная часть: витрина, страница квартиры, бронь гостя без регистрации (ТЗ 3.3)."""
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Account, Apartment, Booking, BookingStatus as S, Review, now_utc
from ..schemas import (
    BusyRange, CancelIn, GuestBookingIn, GuestBookingOut, PublicAccountOut, PublicApartmentCard,
    PublicApartmentOut, PublicReview, QuoteIn, QuoteOut, ReviewIn,
)
from ..services import booking as svc
from ..services import notify
from ..services.files import RECEIPT_EXT, save_upload

router = APIRouter(prefix="/public", tags=["public"])

SHOW_ADDRESS = {S.CONFIRMED.value, S.CHECKED_IN.value, S.CHECKED_OUT.value, S.CLOSED.value}


def _account(db: Session, slug: str) -> Account:
    acc = db.scalar(select(Account).where(Account.slug == slug))
    if acc is None or acc.is_blocked:
        raise HTTPException(404, "Страница не найдена")
    return acc


def _apartment(db: Session, slug: str, apt_slug: str) -> Apartment:
    acc = _account(db, slug)
    apt = db.scalar(select(Apartment).where(Apartment.account_id == acc.id, Apartment.slug == apt_slug))
    if apt is None or not apt.is_active:
        raise HTTPException(404, "Квартира не найдена")
    return apt


def _rating(db: Session, apartment_id: int) -> tuple[float | None, int]:
    avg, cnt = db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.apartment_id == apartment_id)
    ).one()
    return (round(float(avg), 2) if avg is not None else None), cnt


def _booking_by_token(db: Session, token: str) -> Booking:
    b = db.scalar(select(Booking).where(Booking.public_token == token))
    if b is None or b.status == S.BLOCKED.value:
        raise HTTPException(404, "Бронь не найдена")
    return b


def _booking_out(b: Booking) -> GuestBookingOut:
    acc = b.apartment.account
    confirmed = b.status in SHOW_ADDRESS
    return GuestBookingOut(
        token=b.public_token, status=b.status, apartment_title=b.apartment.title,
        check_in=b.start_at, check_out=b.end_at, guests_count=b.guests_count,
        total_price=b.total_price, prepayment_amount=b.prepayment_amount, deposit_amount=b.deposit_amount,
        hold_expires_at=b.hold_expires_at,
        payment_details=acc.payment_details if b.status == S.AWAITING_PAYMENT.value else None,
        payment_qr=acc.payment_qr_path if b.status == S.AWAITING_PAYMENT.value else None,
        address=b.apartment.address if confirmed else None,
        checkin_instructions=b.apartment.checkin_instructions if confirmed else None,
        reject_reason=b.reject_reason,
        can_cancel=b.status in {s.value for s in svc.CANCELLABLE},
        free_cancel_until=svc.free_cancel_until(b),
        can_review=b.status in (S.CHECKED_OUT.value, S.CLOSED.value) and b.review is None,
    )


@router.get("/b/{token}", response_model=GuestBookingOut)
def booking_page(token: str, db: Session = Depends(get_db)):
    svc.expire_stale(db)
    db.commit()
    return _booking_out(_booking_by_token(db, token))


@router.post("/b/{token}/receipt", response_model=GuestBookingOut)
def upload_receipt(token: str, bg: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    b = _booking_by_token(db, token)
    if b.status != S.AWAITING_PAYMENT.value:
        raise HTTPException(409, "Чек можно загрузить только для брони, ожидающей оплаты")
    path = save_upload(file, "private/receipts", RECEIPT_EXT)
    try:
        svc.attach_receipt(db, b, path)
    except svc.BookingError:
        db.commit()  # фиксируем перевод в «истекла»
        raise
    text = f"🧾 Чек по брони #{b.id}: {notify.describe(b)}. Предоплата {b.prepayment_amount:.0f} сом."
    if b.guest and b.guest.is_blacklisted:
        text += f"\n⚠️ Гость в чёрном списке: {b.guest.blacklist_reason or 'без причины'}"
    notify.record(db, b.account_id, "receipt", text, b)
    chats = notify.staff_chat_ids(db, b.account_id)
    db.commit()
    bg.add_task(notify.send_telegram, chats, text, notify.payment_buttons(b.id))
    return _booking_out(b)


@router.post("/b/{token}/cancel", response_model=GuestBookingOut)
def guest_cancel(token: str, data: CancelIn, bg: BackgroundTasks, db: Session = Depends(get_db)):
    b = _booking_by_token(db, token)
    svc.cancel(db, b, reason=data.reason, actor="гость")
    text = f"🚫 Гость отменил бронь #{b.id}: {notify.describe(b)}." + (
        " Предоплату нужно вернуть." if b.refund_due else "")
    notify.record(db, b.account_id, "cancel", text, b)
    chats = notify.staff_chat_ids(db, b.account_id)
    db.commit()
    bg.add_task(notify.send_telegram, chats, text)
    return _booking_out(b)


@router.post("/b/{token}/review", status_code=201)
def leave_review(token: str, data: ReviewIn, bg: BackgroundTasks, db: Session = Depends(get_db)):
    b = _booking_by_token(db, token)
    if b.status not in (S.CHECKED_OUT.value, S.CLOSED.value):
        raise HTTPException(409, "Отзыв можно оставить после выезда")
    if b.review is not None:
        raise HTTPException(409, "Отзыв по этой брони уже оставлен")
    db.add(Review(booking_id=b.id, apartment_id=b.apartment_id, rating=data.rating, text=data.text))
    text = f"⭐ Новый отзыв {data.rating}/5 по «{b.apartment.title}»"
    notify.record(db, b.account_id, "review", text, b)
    chats = notify.staff_chat_ids(db, b.account_id)
    db.commit()
    bg.add_task(notify.send_telegram, chats, text)
    return {"ok": True}


@router.get("/{slug}", response_model=PublicAccountOut)
def storefront(slug: str, db: Session = Depends(get_db)):
    acc = _account(db, slug)
    cards = []
    for apt in db.scalars(select(Apartment).where(Apartment.account_id == acc.id, Apartment.is_active)
                          .order_by(Apartment.id)):
        rating, cnt = _rating(db, apt.id)
        cards.append(PublicApartmentCard(slug=apt.slug, title=apt.title, district=apt.district,
                                         price_per_night=apt.price_per_night, rating=rating, reviews_count=cnt,
                                         cover=apt.photos[0].path if apt.photos else None))
    return PublicAccountOut(slug=acc.slug, name=acc.name, apartments=cards)


@router.get("/{slug}/{apt_slug}", response_model=PublicApartmentOut)
def apartment_page(slug: str, apt_slug: str, db: Session = Depends(get_db)):
    apt = _apartment(db, slug, apt_slug)
    svc.expire_stale(db)
    db.commit()
    rating, _ = _rating(db, apt.id)
    reviews = db.execute(
        select(Review, Booking).join(Booking, Booking.id == Review.booking_id)
        .where(Review.apartment_id == apt.id).order_by(Review.created_at.desc()).limit(50)
    ).all()
    now = now_utc()
    busy = svc.busy_ranges(db, apt.id, now, now + timedelta(days=180))
    return PublicApartmentOut(
        slug=apt.slug, title=apt.title, district=apt.district, lat=apt.lat, lng=apt.lng,
        description=apt.description, amenities=apt.amenities, rules=apt.rules,
        price_per_night=apt.price_per_night, weekend_price=apt.weekend_price, min_nights=apt.min_nights,
        max_guests=apt.max_guests, check_in_time=apt.check_in_time, check_out_time=apt.check_out_time,
        prepayment=apt.prepayment, deposit=apt.deposit, free_cancel_days=apt.free_cancel_days,
        photos=[p.path for p in apt.photos], rating=rating,
        reviews=[PublicReview(rating=r.rating, text=r.text, owner_reply=r.owner_reply,
                              guest_name=(bk.guest.name.split()[0] if bk.guest else "Гость"),
                              created_at=r.created_at) for r, bk in reviews],
        busy=[BusyRange(start_at=s, end_at=e) for s, e in busy],
    )


@router.post("/{slug}/{apt_slug}/quote", response_model=QuoteOut)
def get_quote(slug: str, apt_slug: str, data: QuoteIn, db: Session = Depends(get_db)):
    apt = _apartment(db, slug, apt_slug)
    q = svc.quote(db, apt, data.check_in, data.check_out)
    return QuoteOut(nights=q.nights, total=q.total, prepayment=q.prepayment, deposit=q.deposit, breakdown=q.breakdown)


@router.post("/{slug}/{apt_slug}/bookings", response_model=GuestBookingOut, status_code=201)
def guest_book(slug: str, apt_slug: str, data: GuestBookingIn, bg: BackgroundTasks, db: Session = Depends(get_db)):
    apt = _apartment(db, slug, apt_slug)
    b, guest = svc.create_guest_booking(
        db, apt, name=data.name, phone=data.phone, check_in=data.check_in, check_out=data.check_out,
        guests_count=data.guests_count, source=data.source,
    )
    db.refresh(b)
    text = f"🆕 Новая бронь #{b.id}: {notify.describe(b)}. Ждём чек."
    if guest.is_blacklisted:
        text += f"\n⚠️ Гость в чёрном списке: {guest.blacklist_reason or 'без причины'}"
    notify.record(db, b.account_id, "new_booking", text, b)
    chats = notify.staff_chat_ids(db, b.account_id)
    db.commit()
    bg.add_task(notify.send_telegram, chats, text)
    return _booking_out(b)
