"""Аналитика владельца за период (ТЗ 3.5.3).

Выручка и ночи считаются по пересечению брони с периодом: бронь 30.11–03.12
при периоде «ноябрь» даёт 1 ночь и 1/3 своей суммы. Так сумма по месяцам
сходится с общей суммой.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Apartment, Booking, BookingStatus as S, Expense

EARNING = (S.CONFIRMED.value, S.CHECKED_IN.value, S.CHECKED_OUT.value, S.CLOSED.value)
CENT = Decimal("0.01")


def _nights_between(start: datetime, end: datetime) -> list[date]:
    """Ночи брони = календарные даты заезда .. день до выезда (по местному времени)."""
    d0 = start.astimezone(settings.tz).date()
    d1 = end.astimezone(settings.tz).date()
    return [d0 + timedelta(days=i) for i in range((d1 - d0).days)]


def summary(db: Session, account_id: int, frm: date, to: date) -> dict:
    """Период [frm, to] включительно."""
    days = (to - frm).days + 1
    apartments = db.scalars(select(Apartment).where(Apartment.account_id == account_id).order_by(Apartment.id)).all()
    period_start = datetime.combine(frm, datetime.min.time(), tzinfo=settings.tz)
    period_end = datetime.combine(to + timedelta(days=1), datetime.min.time(), tzinfo=settings.tz)

    bookings = db.scalars(
        select(Booking).where(
            Booking.account_id == account_id,
            Booking.status != S.BLOCKED.value,
            Booking.start_at < period_end,
            Booking.end_at > period_start,
        )
    ).all()

    per_apt = {a.id: {"apartment_id": a.id, "title": a.title, "nights": 0, "revenue": Decimal("0"),
                      "expenses": Decimal("0")} for a in apartments}
    by_source: dict[str, dict] = defaultdict(lambda: {"bookings": 0, "revenue": Decimal("0")})
    created = cancelled = expired = 0

    for b in bookings:
        if b.status == S.CANCELLED.value:
            cancelled += 1
        elif b.status == S.EXPIRED.value:
            expired += 1
        created += 1
        if b.status not in EARNING:
            continue
        all_nights = _nights_between(b.start_at, b.end_at)
        in_period = [n for n in all_nights if frm <= n <= to]
        if not all_nights or not in_period:
            continue
        share = (b.total_price * len(in_period) / len(all_nights)).quantize(CENT, ROUND_HALF_UP)
        row = per_apt.get(b.apartment_id)
        if row is not None:
            row["nights"] += len(in_period)
            row["revenue"] += share
        by_source[b.source]["bookings"] += 1
        by_source[b.source]["revenue"] += share

    for apt_id, total in db.execute(
        select(Expense.apartment_id, func.sum(Expense.amount)).where(
            Expense.account_id == account_id, Expense.spent_on >= frm, Expense.spent_on <= to
        ).group_by(Expense.apartment_id)
    ):
        if apt_id in per_apt:
            per_apt[apt_id]["expenses"] = Decimal(total)

    rows = []
    for row in per_apt.values():
        row["occupancy_pct"] = round(100 * row["nights"] / days, 1) if days else 0.0
        row["profit"] = row["revenue"] - row["expenses"]
        row["avg_night_price"] = (row["revenue"] / row["nights"]).quantize(CENT) if row["nights"] else None
        rows.append(row)

    total_nights = sum(r["nights"] for r in rows)
    total_revenue = sum((r["revenue"] for r in rows), Decimal("0"))
    total_expenses = sum((r["expenses"] for r in rows), Decimal("0"))
    capacity = days * len(apartments)
    return {
        "from": frm, "to": to, "days": days,
        "totals": {
            "occupancy_pct": round(100 * total_nights / capacity, 1) if capacity else 0.0,
            "nights": total_nights,
            "revenue": total_revenue,
            "expenses": total_expenses,
            "profit": total_revenue - total_expenses,
            "avg_night_price": (total_revenue / total_nights).quantize(CENT) if total_nights else None,
            "bookings_created": created,
            "cancelled_pct": round(100 * cancelled / created, 1) if created else 0.0,
            "expired_pct": round(100 * expired / created, 1) if created else 0.0,
        },
        "apartments": rows,
        "sources": [{"source": k, **v} for k, v in sorted(by_source.items())],
    }
