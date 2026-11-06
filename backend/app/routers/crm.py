"""Гости, расходы, аналитика, отзывы, уведомления, выгрузка."""
import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Booking, Expense, Guest, Notification, Review, User
from ..schemas import ExpenseIn, ExpenseOut, GuestOut, GuestPatch, NotificationOut, ReviewReplyIn
from ..security import owner_only, staff
from ..services import analytics
from .apartments import get_own_apartment

router = APIRouter(tags=["crm"])


# ---------- гости ----------
@router.get("/guests")
def list_guests(user: User = Depends(staff), db: Session = Depends(get_db),
                q: str | None = Query(default=None, max_length=60), blacklisted: bool | None = None):
    stmt = (
        select(Guest, func.count(Booking.id), func.coalesce(func.sum(Booking.total_price), 0))
        .join(Booking, Booking.guest_id == Guest.id, isouter=True)
        .where(Guest.account_id == user.account_id).group_by(Guest.id).order_by(Guest.created_at.desc())
    )
    if q:
        stmt = stmt.where(Guest.name.ilike(f"%{q}%") | Guest.phone.ilike(f"%{q}%"))
    if blacklisted is not None:
        stmt = stmt.where(Guest.is_blacklisted == blacklisted)
    return [{**GuestOut.model_validate(g).model_dump(), "bookings": n, "total_spent": total}
            for g, n, total in db.execute(stmt)]


def own_guest(db: Session, user: User, guest_id: int) -> Guest:
    g = db.get(Guest, guest_id)
    if g is None or g.account_id != user.account_id:
        raise HTTPException(404, "Гость не найден")
    return g


@router.get("/guests/{guest_id}")
def get_guest(guest_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    g = own_guest(db, user, guest_id)
    bookings = db.scalars(select(Booking).where(Booking.guest_id == g.id).order_by(Booking.start_at.desc())).all()
    reviews = db.scalars(select(Review).join(Booking).where(Booking.guest_id == g.id)).all()
    return {**GuestOut.model_validate(g).model_dump(),
            "bookings": [{"id": b.id, "apartment_id": b.apartment_id, "start_at": b.start_at, "end_at": b.end_at,
                          "status": b.status, "total_price": b.total_price} for b in bookings],
            "reviews": [{"rating": r.rating, "text": r.text} for r in reviews]}


@router.patch("/guests/{guest_id}", response_model=GuestOut)
def patch_guest(guest_id: int, data: GuestPatch, user: User = Depends(staff), db: Session = Depends(get_db)):
    g = own_guest(db, user, guest_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(g, k, v)
    if data.is_blacklisted is False:
        g.blacklist_reason = None
    db.commit()
    return g


# ---------- отзывы ----------
@router.get("/reviews")
def list_reviews(user: User = Depends(staff), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Review, Booking).join(Booking, Booking.id == Review.booking_id)
        .where(Booking.account_id == user.account_id).order_by(Review.created_at.desc()).limit(200)
    ).all()
    return [{"id": r.id, "booking_id": b.id, "apartment_id": b.apartment_id, "apartment_title": b.apartment.title,
             "guest_name": b.guest.name if b.guest else "Гость", "rating": r.rating, "text": r.text,
             "owner_reply": r.owner_reply, "created_at": r.created_at} for r, b in rows]


@router.post("/reviews/{review_id}/reply")
def reply_review(review_id: int, data: ReviewReplyIn, user: User = Depends(owner_only), db: Session = Depends(get_db)):
    r = db.get(Review, review_id)
    if r is None or r.booking.account_id != user.account_id:
        raise HTTPException(404, "Отзыв не найден")
    r.owner_reply = data.reply  # сам отзыв владелец изменить или удалить не может (ТЗ 3.3.5)
    db.commit()
    return {"ok": True}


# ---------- расходы и аналитика (только владелец) ----------
@router.get("/expenses", response_model=list[ExpenseOut])
def list_expenses(user: User = Depends(owner_only), db: Session = Depends(get_db),
                  date_from: date | None = None, date_to: date | None = None, apartment_id: int | None = None):
    stmt = select(Expense).where(Expense.account_id == user.account_id).order_by(Expense.spent_on.desc())
    if date_from:
        stmt = stmt.where(Expense.spent_on >= date_from)
    if date_to:
        stmt = stmt.where(Expense.spent_on <= date_to)
    if apartment_id:
        stmt = stmt.where(Expense.apartment_id == apartment_id)
    return db.scalars(stmt).all()


@router.post("/expenses", response_model=ExpenseOut, status_code=201)
def add_expense(data: ExpenseIn, user: User = Depends(owner_only), db: Session = Depends(get_db)):
    get_own_apartment(db, user, data.apartment_id)
    e = Expense(account_id=user.account_id, **data.model_dump())
    db.add(e)
    db.commit()
    return e


@router.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int, user: User = Depends(owner_only), db: Session = Depends(get_db)):
    e = db.get(Expense, expense_id)
    if e is None or e.account_id != user.account_id:
        raise HTTPException(404, "Расход не найден")
    db.delete(e)
    db.commit()


@router.get("/analytics")
def get_analytics(date_from: date, date_to: date, user: User = Depends(owner_only), db: Session = Depends(get_db)):
    if date_to < date_from or (date_to - date_from).days > 366:
        raise HTTPException(422, "Период — от 1 дня до года")
    return analytics.summary(db, user.account_id, date_from, date_to)


@router.get("/export/bookings.csv")
def export_bookings(user: User = Depends(owner_only), db: Session = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "квартира", "гость", "телефон", "заезд", "выезд", "статус", "источник", "сумма",
                "предоплата", "залог", "залог_статус", "удержано"])
    rows = db.scalars(select(Booking).where(Booking.account_id == user.account_id).order_by(Booking.start_at))
    for b in rows:
        w.writerow([b.id, b.apartment.title, b.guest.name if b.guest else "", b.guest.phone if b.guest else "",
                    b.start_at.astimezone(settings.tz).isoformat(), b.end_at.astimezone(settings.tz).isoformat(),
                    b.status, b.source, b.total_price, b.prepayment_amount, b.deposit_amount, b.deposit_status,
                    b.deposit_withheld])
    data = "﻿" + buf.getvalue()  # BOM — чтобы Excel открыл кириллицу
    return StreamingResponse(iter([data]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=bookings.csv"})


# ---------- уведомления в CRM ----------
@router.get("/notifications", response_model=list[NotificationOut])
def notifications(user: User = Depends(staff), db: Session = Depends(get_db), unread: bool = False):
    stmt = select(Notification).where(Notification.account_id == user.account_id)
    if unread:
        stmt = stmt.where(Notification.is_read.is_(False))
    return db.scalars(stmt.order_by(Notification.id.desc()).limit(100)).all()


@router.post("/notifications/read-all", status_code=204)
def read_all(user: User = Depends(staff), db: Session = Depends(get_db)):
    for n in db.scalars(select(Notification).where(Notification.account_id == user.account_id,
                                                    Notification.is_read.is_(False))):
        n.is_read = True
    db.commit()
