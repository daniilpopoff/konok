"""Модель данных Konok. Деньги — Numeric(12,2), время — timestamptz (UTC в базе)."""
import enum
import secrets
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import (
    DDL,
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    OWNER = "owner"
    MANAGER = "manager"
    ADMIN = "admin"


class BookingStatus(str, enum.Enum):
    AWAITING_PAYMENT = "awaiting_payment"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    BLOCKED = "blocked"  # ручная блокировка дат владельцем


# Статусы, которые НЕ занимают даты в календаре
FREEING_STATUSES = (BookingStatus.CANCELLED.value, BookingStatus.EXPIRED.value)


class Source(str, enum.Enum):
    LALAFO = "lalafo"
    INSTAGRAM = "instagram"
    DIRECT = "direct"
    MANUAL = "manual"
    OTHER = "other"


class DepositStatus(str, enum.Enum):
    NONE = "none"
    RECEIVED = "received"
    RETURNED = "returned"
    WITHHELD = "withheld"


class ExpenseCategory(str, enum.Enum):
    CLEANING = "cleaning"
    UTILITIES = "utilities"
    REPAIR = "repair"
    SUPPLIES = "supplies"
    OTHER = "other"


class Account(Base):
    """Арендный бизнес одного владельца (tenant). Все данные изолированы по account_id."""

    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)  # konok.kg/{slug}
    name: Mapped[str] = mapped_column(String(120))
    payment_details: Mapped[str] = mapped_column(Text, default="")
    payment_qr_path: Mapped[str | None] = mapped_column(String(255))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    users: Mapped[list["User"]] = relationship(back_populates="account")
    apartments: Mapped[list["Apartment"]] = relationship(back_populates="account")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16))
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32), index=True)
    telegram_link_code: Mapped[str | None] = mapped_column(String(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    account: Mapped[Account | None] = relationship(back_populates="users")


class Apartment(Base):
    __tablename__ = "apartments"
    __table_args__ = (
        UniqueConstraint("account_id", "slug"),
        CheckConstraint("price_per_night > 0", name="price_positive"),
        CheckConstraint("min_nights >= 1", name="min_nights_positive"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(160))
    district: Mapped[str] = mapped_column(String(120), default="")
    address: Mapped[str] = mapped_column(String(255), default="")  # виден гостю только после подтверждения
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    description: Mapped[str] = mapped_column(Text, default="")
    amenities: Mapped[list] = mapped_column(JSON, default=list)
    rules: Mapped[str] = mapped_column(Text, default="")
    checkin_instructions: Mapped[str] = mapped_column(Text, default="")
    price_per_night: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    weekend_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # ночи пт→сб и сб→вс
    min_nights: Mapped[int] = mapped_column(Integer, default=1)
    max_guests: Mapped[int] = mapped_column(Integer, default=2)
    check_in_time: Mapped[time] = mapped_column(Time, default=time(14, 0))
    check_out_time: Mapped[time] = mapped_column(Time, default=time(12, 0))
    prepayment: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("1000"))
    deposit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    free_cancel_days: Mapped[int] = mapped_column(Integer, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    account: Mapped[Account] = relationship(back_populates="apartments")
    photos: Mapped[list["ApartmentPhoto"]] = relationship(
        order_by="ApartmentPhoto.position", cascade="all, delete-orphan"
    )
    price_overrides: Mapped[list["PriceOverride"]] = relationship(cascade="all, delete-orphan")


class ApartmentPhoto(Base):
    __tablename__ = "apartment_photos"
    id: Mapped[int] = mapped_column(primary_key=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer, default=0)


class PriceOverride(Base):
    """Особая цена на конкретную дату (праздники и т.п.)."""

    __tablename__ = "price_overrides"
    __table_args__ = (UniqueConstraint("apartment_id", "night"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id", ondelete="CASCADE"), index=True)
    night: Mapped[date] = mapped_column(Date)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class Guest(Base):
    __tablename__ = "guests"
    __table_args__ = (UniqueConstraint("account_id", "phone"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(32))
    notes: Mapped[str] = mapped_column(Text, default="")
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)
    blacklist_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


def _new_token() -> str:
    return secrets.token_urlsafe(24)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="booking_range_valid"),
        CheckConstraint("guests_count >= 1", name="booking_guests_positive"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id", ondelete="CASCADE"), index=True)
    guest_id: Mapped[int | None] = mapped_column(ForeignKey("guests.id", ondelete="SET NULL"), index=True)
    public_token: Mapped[str] = mapped_column(String(48), unique=True, default=_new_token)
    # Дата И время — чтобы позже добавить почасовую аренду без смены модели (ТЗ 3.2.4)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    guests_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), index=True)
    source: Mapped[str] = mapped_column(String(16), default=Source.DIRECT.value)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    prepayment_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    deposit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    balance_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    deposit_status: Mapped[str] = mapped_column(String(16), default=DepositStatus.NONE.value)
    deposit_withheld: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    deposit_note: Mapped[str | None] = mapped_column(Text)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    receipt_path: Mapped[str | None] = mapped_column(String(255))
    reject_reason: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    refund_due: Mapped[bool] = mapped_column(Boolean, default=False)
    refunded: Mapped[bool] = mapped_column(Boolean, default=False)
    block_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    apartment: Mapped[Apartment] = relationship()
    guest: Mapped[Guest | None] = relationship()
    events: Mapped[list["BookingEvent"]] = relationship(
        order_by="BookingEvent.id", cascade="all, delete-orphan", back_populates="booking"
    )
    review: Mapped["Review | None"] = relationship(back_populates="booking", uselist=False)


# Главная гарантия ТЗ 3.2.3: две активные брони одной квартиры не могут пересекаться.
# Проверяет сама PostgreSQL, поэтому работает и при одновременных запросах.
event.listen(
    Booking.__table__,
    "after_create",
    DDL(
        "ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap EXCLUDE USING gist "
        "(apartment_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&) "
        "WHERE (status NOT IN ('cancelled', 'expired'))"
    ),
)


class BookingEvent(Base):
    """История переходов статусов: кто, когда, что."""

    __tablename__ = "booking_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    booking: Mapped[Booking] = relationship(back_populates="events")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), unique=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    owner_reply: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    booking: Mapped[Booking] = relationship(back_populates="review")


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (CheckConstraint("amount > 0", name="expense_positive"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    apartment_id: Mapped[int] = mapped_column(ForeignKey("apartments.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(16))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    spent_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, default="")


class Notification(Base):
    """Те же события, что уходят в Telegram, видны внутри CRM (ТЗ 3.5.4)."""

    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
