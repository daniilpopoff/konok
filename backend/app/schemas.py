from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

SLUG = r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])?$"
PHONE = r"^\+?[0-9 ()-]{9,20}$"


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    business_name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=SLUG)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORM):
    id: int
    email: str
    name: str
    role: str
    account_id: int | None
    telegram_linked: bool = False


class ManagerIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)


class AccountSettingsIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    payment_details: str | None = Field(default=None, max_length=2000)


# ---------- apartments ----------
class ApartmentIn(BaseModel):
    slug: str = Field(pattern=SLUG)
    title: str = Field(min_length=1, max_length=160)
    district: str = Field(default="", max_length=120)
    address: str = Field(default="", max_length=255)
    lat: Decimal | None = None
    lng: Decimal | None = None
    description: str = Field(default="", max_length=8000)
    amenities: list[str] = Field(default_factory=list, max_length=50)
    rules: str = Field(default="", max_length=4000)
    checkin_instructions: str = Field(default="", max_length=4000)
    price_per_night: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    weekend_price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    min_nights: int = Field(default=1, ge=1, le=60)
    max_guests: int = Field(default=2, ge=1, le=30)
    check_in_time: time = time(14, 0)
    check_out_time: time = time(12, 0)
    prepayment: Decimal = Field(default=Decimal("1000"), ge=0, max_digits=12, decimal_places=2)
    deposit: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    free_cancel_days: int = Field(default=3, ge=0, le=60)
    is_active: bool = True


class ApartmentPatch(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    district: str | None = None
    address: str | None = None
    description: str | None = None
    amenities: list[str] | None = None
    rules: str | None = None
    checkin_instructions: str | None = None
    price_per_night: Decimal | None = Field(default=None, gt=0)
    weekend_price: Decimal | None = Field(default=None, gt=0)
    min_nights: int | None = Field(default=None, ge=1)
    max_guests: int | None = Field(default=None, ge=1)
    prepayment: Decimal | None = Field(default=None, ge=0)
    deposit: Decimal | None = Field(default=None, ge=0)
    free_cancel_days: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class PhotoOut(ORM):
    id: int
    path: str
    position: int


class ApartmentOut(ORM):
    id: int
    slug: str
    title: str
    district: str
    address: str
    description: str
    amenities: list[str]
    rules: str
    checkin_instructions: str
    price_per_night: Decimal
    weekend_price: Decimal | None
    min_nights: int
    max_guests: int
    check_in_time: time
    check_out_time: time
    prepayment: Decimal
    deposit: Decimal
    free_cancel_days: int
    is_active: bool
    photos: list[PhotoOut] = []


class PriceOverrideIn(BaseModel):
    night: date
    price: Decimal = Field(gt=0)


# ---------- public ----------
class PublicApartmentCard(BaseModel):
    slug: str
    title: str
    district: str
    price_per_night: Decimal
    rating: float | None
    reviews_count: int
    cover: str | None


class PublicAccountOut(BaseModel):
    slug: str
    name: str
    apartments: list[PublicApartmentCard]


class PublicReview(BaseModel):
    rating: int
    text: str
    owner_reply: str | None
    guest_name: str
    created_at: datetime


class BusyRange(BaseModel):
    start_at: datetime
    end_at: datetime


class PublicApartmentOut(BaseModel):
    slug: str
    title: str
    district: str
    lat: Decimal | None
    lng: Decimal | None
    description: str
    amenities: list[str]
    rules: str
    price_per_night: Decimal
    weekend_price: Decimal | None
    min_nights: int
    max_guests: int
    check_in_time: time
    check_out_time: time
    prepayment: Decimal
    deposit: Decimal
    free_cancel_days: int
    photos: list[str]
    rating: float | None
    reviews: list[PublicReview]
    busy: list[BusyRange]


class QuoteIn(BaseModel):
    check_in: date
    check_out: date


class QuoteOut(BaseModel):
    nights: int
    total: Decimal
    prepayment: Decimal
    deposit: Decimal
    breakdown: list[dict]


class GuestBookingIn(BaseModel):
    check_in: date
    check_out: date
    guests_count: int = Field(default=1, ge=1, le=30)
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(pattern=PHONE)
    consent: bool
    source: str = "direct"

    @field_validator("consent")
    @classmethod
    def must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Нужно согласие на обработку персональных данных")
        return v


class GuestBookingOut(BaseModel):
    token: str
    status: str
    apartment_title: str
    check_in: datetime
    check_out: datetime
    guests_count: int
    total_price: Decimal
    prepayment_amount: Decimal
    deposit_amount: Decimal
    hold_expires_at: datetime | None
    payment_details: str | None
    payment_qr: str | None
    address: str | None  # только после подтверждения
    checkin_instructions: str | None
    reject_reason: str | None
    can_cancel: bool
    free_cancel_until: datetime
    can_review: bool


class CancelIn(BaseModel):
    reason: str = Field(default="", max_length=1000)


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str = Field(default="", max_length=4000)


# ---------- staff bookings ----------
class GuestOut(ORM):
    id: int
    name: str
    phone: str
    notes: str
    is_blacklisted: bool
    blacklist_reason: str | None


class EventOut(ORM):
    from_status: str | None
    to_status: str
    actor: str
    note: str | None
    created_at: datetime


class BookingOut(ORM):
    id: int
    apartment_id: int
    guest: GuestOut | None
    start_at: datetime
    end_at: datetime
    guests_count: int
    status: str
    source: str
    total_price: Decimal
    prepayment_amount: Decimal
    deposit_amount: Decimal
    balance_paid: bool
    deposit_status: str
    deposit_withheld: Decimal
    deposit_note: str | None
    hold_expires_at: datetime | None
    has_receipt: bool
    reject_reason: str | None
    cancel_reason: str | None
    refund_due: bool
    refunded: bool
    block_reason: str | None
    created_at: datetime


class BookingDetailOut(BookingOut):
    events: list[EventOut]
    guest_link: str


class ManualBookingIn(BaseModel):
    apartment_id: int
    check_in: date
    check_out: date
    guests_count: int = Field(default=1, ge=1)
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(pattern=PHONE)
    status: Literal["awaiting_payment", "confirmed"] = "confirmed"
    total_price: Decimal | None = Field(default=None, ge=0)


class BlockIn(BaseModel):
    apartment_id: int
    check_in: date
    check_out: date
    reason: str = Field(min_length=1, max_length=500)


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class CheckInIn(BaseModel):
    balance_paid: bool = True
    deposit_received: bool = True


class DepositIn(BaseModel):
    action: Literal["returned", "withheld"]
    withheld_amount: Decimal = Field(default=Decimal("0"), ge=0)
    note: str = Field(default="", max_length=1000)


class GuestPatch(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)
    is_blacklisted: bool | None = None
    blacklist_reason: str | None = Field(default=None, max_length=1000)


class ReviewReplyIn(BaseModel):
    reply: str = Field(min_length=1, max_length=2000)


class ExpenseIn(BaseModel):
    apartment_id: int
    category: Literal["cleaning", "utilities", "repair", "supplies", "other"]
    amount: Decimal = Field(gt=0)
    spent_on: date
    note: str = Field(default="", max_length=1000)


class ExpenseOut(ORM):
    id: int
    apartment_id: int
    category: str
    amount: Decimal
    spent_on: date
    note: str


class NotificationOut(ORM):
    id: int
    booking_id: int | None
    kind: str
    text: str
    is_read: bool
    created_at: datetime
