"""Брони в CRM: список, шахматка, ручные брони, подтверждение, заселение, залог (ТЗ 3.4, 3.5)."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..db import get_db
from ..models import FREEING_STATUSES, Apartment, Booking, Guest, User
from ..schemas import (
    BlockIn, BookingDetailOut, BookingOut, CancelIn, CheckInIn, DepositIn, ManualBookingIn, RejectIn,
)
from ..security import staff
from ..services import booking as svc
from ..services import notify
from ..services.files import abs_path
from .apartments import get_own_apartment

router = APIRouter(prefix="/bookings", tags=["bookings"])


def actor_of(user: User) -> str:
    return f"{user.name} ({user.role})"


def own_booking(db: Session, user: User, booking_id: int) -> Booking:
    b = db.get(Booking, booking_id)
    if b is None or b.account_id != user.account_id:
        raise HTTPException(404, "Бронь не найдена")
    return b


def to_out(b: Booking, cls=BookingOut):
    data = {**{k: getattr(b, k) for k in BookingOut.model_fields if hasattr(b, k)},
            "guest": b.guest, "has_receipt": b.receipt_path is not None}
    if cls is BookingDetailOut:
        data["events"] = b.events
        data["guest_link"] = f"{settings.public_base_url}/b/{b.public_token}"
    return cls.model_validate(data)


@router.get("", response_model=list[BookingOut])
def list_bookings(
    user: User = Depends(staff), db: Session = Depends(get_db),
    status: list[str] | None = Query(default=None), apartment_id: int | None = None,
    source: str | None = None, date_from: date | None = None, date_to: date | None = None,
    q: str | None = Query(default=None, max_length=60), limit: int = Query(default=100, le=500), offset: int = 0,
):
    svc.expire_stale(db)
    db.commit()
    stmt = (select(Booking).options(selectinload(Booking.guest))
            .where(Booking.account_id == user.account_id).order_by(Booking.start_at.desc()))
    if status:
        stmt = stmt.where(Booking.status.in_(status))
    if apartment_id:
        stmt = stmt.where(Booking.apartment_id == apartment_id)
    if source:
        stmt = stmt.where(Booking.source == source)
    if date_from:
        stmt = stmt.where(Booking.end_at > datetime.combine(date_from, datetime.min.time(), tzinfo=settings.tz))
    if date_to:
        stmt = stmt.where(Booking.start_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time(),
                                                              tzinfo=settings.tz))
    if q:
        stmt = stmt.join(Guest, isouter=True).where(or_(Guest.name.ilike(f"%{q}%"), Guest.phone.ilike(f"%{q}%")))
    return [to_out(b) for b in db.scalars(stmt.limit(limit).offset(offset))]


@router.get("/calendar")
def calendar(date_from: date, date_to: date, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Данные для шахматки: квартиры строками, брони полосками."""
    if (date_to - date_from).days > 92 or date_to < date_from:
        raise HTTPException(422, "Период — от 1 до 92 дней")
    svc.expire_stale(db)
    db.commit()
    frm = datetime.combine(date_from, datetime.min.time(), tzinfo=settings.tz)
    to = datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=settings.tz)
    apts = db.scalars(select(Apartment).where(Apartment.account_id == user.account_id).order_by(Apartment.id)).all()
    rows = db.scalars(
        select(Booking).options(selectinload(Booking.guest)).where(
            Booking.account_id == user.account_id, Booking.status.not_in(FREEING_STATUSES),
            Booking.start_at < to, Booking.end_at > frm,
        )
    ).all()
    by_apt: dict[int, list] = {a.id: [] for a in apts}
    for b in rows:
        by_apt.setdefault(b.apartment_id, []).append({
            "id": b.id, "status": b.status, "start_at": b.start_at, "end_at": b.end_at,
            "guest": b.guest.name if b.guest else None, "block_reason": b.block_reason,
            "warning": bool(b.guest and b.guest.is_blacklisted),
        })
    return {"from": date_from, "to": date_to,
            "apartments": [{"id": a.id, "title": a.title, "bookings": by_apt[a.id]} for a in apts]}


@router.get("/{booking_id}", response_model=BookingDetailOut)
def get_booking(booking_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    return to_out(own_booking(db, user, booking_id), BookingDetailOut)


@router.get("/{booking_id}/receipt")
def get_receipt(booking_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    b = own_booking(db, user, booking_id)
    if not b.receipt_path:
        raise HTTPException(404, "Чек не загружен")
    return FileResponse(abs_path(b.receipt_path))


@router.post("", response_model=BookingDetailOut, status_code=201)
def manual_booking(data: ManualBookingIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    apt = get_own_apartment(db, user, data.apartment_id)
    b = svc.create_manual_booking(
        db, apt, name=data.name, phone=data.phone, check_in=data.check_in, check_out=data.check_out,
        guests_count=data.guests_count, status=data.status, total_price=data.total_price, actor=actor_of(user),
    )
    db.commit()
    db.refresh(b)
    return to_out(b, BookingDetailOut)


@router.post("/blocks", response_model=BookingOut, status_code=201)
def block_dates(data: BlockIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    apt = get_own_apartment(db, user, data.apartment_id)
    b = svc.create_block(db, apt, check_in=data.check_in, check_out=data.check_out, reason=data.reason,
                         actor=actor_of(user))
    db.commit()
    return to_out(b)


def _act(db: Session, b: Booking) -> BookingDetailOut:
    db.commit()
    db.refresh(b)
    return to_out(b, BookingDetailOut)


@router.post("/{booking_id}/confirm", response_model=BookingDetailOut)
def confirm(booking_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    b = own_booking(db, user, booking_id)
    svc.confirm_payment(db, b, actor_of(user))
    return _act(db, b)


@router.post("/{booking_id}/reject", response_model=BookingDetailOut)
def reject(booking_id: int, data: RejectIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    b = own_booking(db, user, booking_id)
    svc.reject_payment(db, b, data.reason, actor_of(user))
    return _act(db, b)


@router.post("/{booking_id}/check-in", response_model=BookingDetailOut)
def do_check_in(booking_id: int, data: CheckInIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    b = own_booking(db, user, booking_id)
    svc.check_in(db, b, balance_paid=data.balance_paid, deposit_received=data.deposit_received, actor=actor_of(user))
    return _act(db, b)


@router.post("/{booking_id}/check-out", response_model=BookingDetailOut)
def do_check_out(booking_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    b = own_booking(db, user, booking_id)
    svc.check_out(db, b, actor_of(user))
    return _act(db, b)


@router.post("/{booking_id}/deposit", response_model=BookingDetailOut)
def deposit(booking_id: int, data: DepositIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    b = own_booking(db, user, booking_id)
    svc.settle_deposit(db, b, action=data.action, withheld=data.withheld_amount, note=data.note, actor=actor_of(user))
    return _act(db, b)


@router.post("/{booking_id}/close", response_model=BookingDetailOut)
def do_close(booking_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    b = own_booking(db, user, booking_id)
    svc.close(db, b, actor_of(user))
    return _act(db, b)


@router.post("/{booking_id}/cancel", response_model=BookingDetailOut)
def staff_cancel(booking_id: int, data: CancelIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    b = own_booking(db, user, booking_id)
    svc.cancel(db, b, reason=data.reason, actor=actor_of(user))
    return _act(db, b)


@router.post("/{booking_id}/refunded", response_model=BookingDetailOut)
def refunded(booking_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    b = own_booking(db, user, booking_id)
    svc.mark_refunded(db, b, actor_of(user))
    return _act(db, b)


@router.get("/{booking_id}/whatsapp")
def whatsapp_link(booking_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Ссылка wa.me с готовым текстом — менеджер отправляет сам (ТЗ 3.5.2)."""
    from urllib.parse import quote as urlquote

    b = own_booking(db, user, booking_id)
    if not b.guest:
        raise HTTPException(404, "У брони нет гостя")
    link = f"{settings.public_base_url}/b/{b.public_token}"
    text = f"Здравствуйте, {b.guest.name}! Ваша бронь «{b.apartment.title}»: {link}"
    return {"url": f"https://wa.me/{b.guest.phone.lstrip('+')}?text={urlquote(text)}"}
