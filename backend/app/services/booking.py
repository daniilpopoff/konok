"""Бизнес-логика броней: расчёт цены, статусы, удержание дат, отмена, залог.

Все переходы статусов идут только через `transition()`, а он сверяется с TRANSITIONS.
Так недопустимый переход отклоняется сервером (ТЗ 3.4.1), а каждый шаг попадает в историю.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    FREEING_STATUSES,
    Apartment,
    Booking,
    BookingEvent,
    BookingStatus as S,
    DepositStatus,
    Guest,
    PriceOverride,
    Source,
    now_utc,
)


class BookingError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


TRANSITIONS: dict[S, set[S]] = {
    S.AWAITING_PAYMENT: {S.AWAITING_CONFIRMATION, S.CANCELLED, S.EXPIRED, S.CONFIRMED},
    S.AWAITING_CONFIRMATION: {S.CONFIRMED, S.AWAITING_PAYMENT, S.CANCELLED},
    S.CONFIRMED: {S.CHECKED_IN, S.CANCELLED},
    S.CHECKED_IN: {S.CHECKED_OUT},
    S.CHECKED_OUT: {S.CLOSED},
    S.BLOCKED: {S.CANCELLED},
    S.CLOSED: set(),
    S.CANCELLED: set(),
    S.EXPIRED: set(),
}

CANCELLABLE = {S.AWAITING_PAYMENT, S.AWAITING_CONFIRMATION, S.CONFIRMED}


# ---------- время ----------
def local_moment(day: date, at) -> datetime:
    """Дата + время заезда/выезда в часовом поясе Бишкека → aware datetime."""
    return datetime.combine(day, at, tzinfo=settings.tz)


def today_local() -> date:
    return datetime.now(settings.tz).date()


def stay_range(apt: Apartment, check_in: date, check_out: date) -> tuple[datetime, datetime]:
    return local_moment(check_in, apt.check_in_time), local_moment(check_out, apt.check_out_time)


# ---------- цена ----------
@dataclass
class Quote:
    nights: int
    total: Decimal
    prepayment: Decimal
    deposit: Decimal
    breakdown: list[dict]


def quote(db: Session, apt: Apartment, check_in: date, check_out: date) -> Quote:
    if check_out <= check_in:
        raise BookingError(422, "Дата выезда должна быть позже даты заезда")
    if check_in < today_local():
        raise BookingError(422, "Нельзя забронировать прошедшие даты")
    nights = (check_out - check_in).days
    if nights < apt.min_nights:
        raise BookingError(422, f"Минимальный срок — {apt.min_nights} ноч.")
    if nights > 90:
        raise BookingError(422, "Максимальный срок — 90 ночей")

    overrides = {
        o.night: o.price
        for o in db.scalars(
            select(PriceOverride).where(
                PriceOverride.apartment_id == apt.id,
                PriceOverride.night >= check_in,
                PriceOverride.night < check_out,
            )
        )
    }
    breakdown, total = [], Decimal("0")
    for i in range(nights):
        night = check_in + timedelta(days=i)
        if night in overrides:
            price, kind = overrides[night], "special"
        elif apt.weekend_price is not None and night.weekday() in (4, 5):  # ночь с пт и с сб
            price, kind = apt.weekend_price, "weekend"
        else:
            price, kind = apt.price_per_night, "regular"
        breakdown.append({"night": night.isoformat(), "price": str(price), "kind": kind})
        total += price
    prepayment = min(apt.prepayment, total)
    return Quote(nights, total, prepayment, apt.deposit, breakdown)


# ---------- служебное ----------
def add_event(db: Session, booking: Booking, frm: str | None, to: str, actor: str, note: str | None = None):
    db.add(BookingEvent(booking=booking, from_status=frm, to_status=to, actor=actor, note=note))


def transition(db: Session, booking: Booking, to: S, actor: str, note: str | None = None) -> None:
    current = S(booking.status)
    if to not in TRANSITIONS[current]:
        raise BookingError(409, f"Нельзя перевести бронь из «{current.value}» в «{to.value}»")
    booking.status = to.value
    add_event(db, booking, current.value, to.value, actor, note)


def expire_stale(db: Session) -> int:
    """Снимает неоплаченные брони, у которых истекло удержание дат. Возвращает число снятых."""
    now = now_utc()
    stale = db.scalars(
        select(Booking)
        .where(Booking.status == S.AWAITING_PAYMENT.value, Booking.hold_expires_at < now)
        .with_for_update(skip_locked=True)
    ).all()
    for b in stale:
        transition(db, b, S.EXPIRED, "система", "Чек не загружен вовремя")
    db.flush()
    return len(stale)


def upsert_guest(db: Session, account_id: int, name: str, phone: str) -> Guest:
    phone = normalize_phone(phone)
    guest = db.scalar(select(Guest).where(Guest.account_id == account_id, Guest.phone == phone))
    if guest is None:
        guest = Guest(account_id=account_id, name=name.strip(), phone=phone)
        db.add(guest)
        db.flush()
    return guest


def normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("0") and len(digits) == 10:  # 0555 123 456 → 996555123456
        digits = "996" + digits[1:]
    return "+" + digits


def _insert_booking(db: Session, booking: Booking) -> Booking:
    """Вставка с перехватом нарушения EXCLUDE-ограничения (пересечение дат)."""
    try:
        with db.begin_nested():
            db.add(booking)
            db.flush()
    except IntegrityError as exc:
        if "bookings_no_overlap" in str(exc.orig):
            raise BookingError(409, "Эти даты уже заняты") from exc
        raise
    return booking


def parse_source(raw: str | None) -> str:
    try:
        return Source((raw or "direct").lower()).value
    except ValueError:
        return Source.OTHER.value


# ---------- создание ----------
def create_guest_booking(
    db: Session, apt: Apartment, *, name: str, phone: str, check_in: date, check_out: date,
    guests_count: int, source: str | None,
) -> tuple[Booking, Guest]:
    if not apt.is_active:
        raise BookingError(404, "Квартира недоступна для бронирования")
    if guests_count > apt.max_guests:
        raise BookingError(422, f"Максимум гостей — {apt.max_guests}")
    expire_stale(db)
    q = quote(db, apt, check_in, check_out)
    guest = upsert_guest(db, apt.account_id, name, phone)
    start_at, end_at = stay_range(apt, check_in, check_out)
    booking = Booking(
        account_id=apt.account_id, apartment_id=apt.id, guest_id=guest.id,
        start_at=start_at, end_at=end_at, guests_count=guests_count,
        status=S.AWAITING_PAYMENT.value, source=parse_source(source),
        total_price=q.total, prepayment_amount=q.prepayment, deposit_amount=q.deposit,
        hold_expires_at=now_utc() + timedelta(minutes=settings.hold_minutes),
    )
    _insert_booking(db, booking)
    add_event(db, booking, None, booking.status, f"гость {guest.name}", "Бронь с витрины")
    return booking, guest


def create_manual_booking(
    db: Session, apt: Apartment, *, name: str, phone: str, check_in: date, check_out: date,
    guests_count: int, status: str, total_price: Decimal | None, actor: str,
) -> Booking:
    if check_out <= check_in:
        raise BookingError(422, "Дата выезда должна быть позже даты заезда")
    expire_stale(db)
    guest = upsert_guest(db, apt.account_id, name, phone)
    start_at, end_at = stay_range(apt, check_in, check_out)
    if total_price is None:
        total_price = quote(db, apt, check_in, check_out).total if check_in >= today_local() else Decimal("0")
    booking = Booking(
        account_id=apt.account_id, apartment_id=apt.id, guest_id=guest.id,
        start_at=start_at, end_at=end_at, guests_count=guests_count, status=status,
        source=Source.MANUAL.value, total_price=total_price,
        prepayment_amount=min(apt.prepayment, total_price), deposit_amount=apt.deposit,
        hold_expires_at=(now_utc() + timedelta(minutes=settings.hold_minutes))
        if status == S.AWAITING_PAYMENT.value else None,
    )
    _insert_booking(db, booking)
    add_event(db, booking, None, status, actor, "Ручная бронь")
    return booking


def create_block(db: Session, apt: Apartment, *, check_in: date, check_out: date, reason: str, actor: str) -> Booking:
    if check_out <= check_in:
        raise BookingError(422, "Дата окончания должна быть позже даты начала")
    expire_stale(db)
    start_at, end_at = stay_range(apt, check_in, check_out)
    booking = Booking(
        account_id=apt.account_id, apartment_id=apt.id, start_at=start_at, end_at=end_at,
        guests_count=1, status=S.BLOCKED.value, source=Source.MANUAL.value, block_reason=reason,
    )
    _insert_booking(db, booking)
    add_event(db, booking, None, booking.status, actor, reason)
    return booking


# ---------- оплата ----------
def attach_receipt(db: Session, booking: Booking, path: str) -> None:
    if booking.status == S.AWAITING_PAYMENT.value and booking.hold_expires_at and booking.hold_expires_at < now_utc():
        transition(db, booking, S.EXPIRED, "система", "Чек не загружен вовремя")
        raise BookingError(410, "Время на оплату истекло, забронируйте заново")
    if booking.status != S.AWAITING_PAYMENT.value:
        raise BookingError(409, "Чек можно загрузить только для брони, ожидающей оплаты")
    booking.receipt_path = path
    booking.hold_expires_at = None
    transition(db, booking, S.AWAITING_CONFIRMATION, "гость", "Чек загружен")


def confirm_payment(db: Session, booking: Booking, actor: str) -> bool:
    """Подтверждение предоплаты. Повтор не меняет статус второй раз (идемпотентно). True — если изменили."""
    if booking.status == S.CONFIRMED.value:
        return False
    if booking.status not in (S.AWAITING_CONFIRMATION.value, S.AWAITING_PAYMENT.value):
        raise BookingError(409, "Эту бронь уже нельзя подтвердить")
    booking.hold_expires_at = None
    booking.reject_reason = None
    transition(db, booking, S.CONFIRMED, actor, "Предоплата подтверждена")
    return True


def reject_payment(db: Session, booking: Booking, reason: str, actor: str) -> None:
    if booking.status != S.AWAITING_CONFIRMATION.value:
        raise BookingError(409, "Отклонить можно только бронь с загруженным чеком")
    booking.reject_reason = reason
    booking.receipt_path = None
    booking.hold_expires_at = now_utc() + timedelta(minutes=settings.hold_minutes)
    transition(db, booking, S.AWAITING_PAYMENT, actor, f"Чек отклонён: {reason}")


# ---------- проживание ----------
def check_in(db: Session, booking: Booking, *, balance_paid: bool, deposit_received: bool, actor: str) -> None:
    transition(db, booking, S.CHECKED_IN, actor)
    booking.balance_paid = balance_paid
    if deposit_received and booking.deposit_amount > 0:
        booking.deposit_status = DepositStatus.RECEIVED.value


def check_out(db: Session, booking: Booking, actor: str) -> None:
    transition(db, booking, S.CHECKED_OUT, actor)


def settle_deposit(db: Session, booking: Booking, *, action: str, withheld: Decimal, note: str, actor: str) -> None:
    if booking.status not in (S.CHECKED_IN.value, S.CHECKED_OUT.value):
        raise BookingError(409, "Залог закрывается во время или после проживания")
    if booking.deposit_status != DepositStatus.RECEIVED.value:
        raise BookingError(409, "Залог не был получен или уже закрыт")
    if action == "withheld":
        if withheld <= 0 or withheld > booking.deposit_amount:
            raise BookingError(422, "Сумма удержания должна быть от 1 до суммы залога")
        if not note.strip():
            raise BookingError(422, "Укажите причину удержания")
        booking.deposit_status = DepositStatus.WITHHELD.value
        booking.deposit_withheld = withheld
    else:
        booking.deposit_status = DepositStatus.RETURNED.value
        booking.deposit_withheld = Decimal("0")
    booking.deposit_note = note or None
    add_event(db, booking, booking.status, booking.status, actor, f"Залог: {action} {withheld if action == 'withheld' else ''}".strip())


def close(db: Session, booking: Booking, actor: str) -> None:
    if booking.deposit_status == DepositStatus.RECEIVED.value:
        raise BookingError(409, "Сначала верните или удержите залог")
    transition(db, booking, S.CLOSED, actor)


# ---------- отмена ----------
def free_cancel_until(booking: Booking) -> datetime:
    return booking.start_at - timedelta(days=booking.apartment.free_cancel_days)


def cancel(db: Session, booking: Booking, *, reason: str, actor: str) -> None:
    current = S(booking.status)
    if current == S.BLOCKED:
        transition(db, booking, S.CANCELLED, actor, reason or "Блокировка снята")
        return
    if current not in CANCELLABLE:
        raise BookingError(409, "Эту бронь уже нельзя отменить")
    prepaid = current in (S.AWAITING_CONFIRMATION, S.CONFIRMED)
    booking.refund_due = prepaid and now_utc() <= free_cancel_until(booking)
    booking.cancel_reason = reason or None
    note = "Предоплата к возврату" if booking.refund_due else ("Предоплата удерживается" if prepaid else None)
    transition(db, booking, S.CANCELLED, actor, " · ".join(x for x in (reason, note) if x) or None)


def mark_refunded(db: Session, booking: Booking, actor: str) -> None:
    if not booking.refund_due or booking.refunded:
        raise BookingError(409, "По этой брони нет возврата к выполнению")
    booking.refunded = True
    add_event(db, booking, booking.status, booking.status, actor, "Предоплата возвращена")


# ---------- занятость ----------
def busy_ranges(db: Session, apartment_id: int, frm: datetime, to: datetime) -> list[tuple[datetime, datetime]]:
    rows = db.execute(
        select(Booking.start_at, Booking.end_at).where(
            Booking.apartment_id == apartment_id,
            Booking.status.not_in(FREEING_STATUSES),
            and_(Booking.start_at < to, Booking.end_at > frm),
        ).order_by(Booking.start_at)
    ).all()
    return [(r.start_at, r.end_at) for r in rows]


def utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)
