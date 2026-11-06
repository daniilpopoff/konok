"""Уведомления: запись в CRM + отправка в Telegram. Сбой Telegram не ломает CRM (ТЗ 3.6.1)."""
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Booking, Notification, Role, User

log = logging.getLogger("konok.notify")


def staff_chat_ids(db: Session, account_id: int) -> list[str]:
    return list(
        db.scalars(
            select(User.telegram_chat_id).where(
                User.account_id == account_id,
                User.role.in_([Role.OWNER.value, Role.MANAGER.value]),
                User.telegram_chat_id.is_not(None),
            )
        )
    )


def record(db: Session, account_id: int, kind: str, text: str, booking: Booking | None = None) -> None:
    db.add(Notification(account_id=account_id, booking_id=booking.id if booking else None, kind=kind, text=text))


def payment_buttons(booking_id: int) -> dict:
    return {
        "inline_keyboard": [[
            {"text": "✅ Подтвердить", "callback_data": f"confirm:{booking_id}"},
            {"text": "❌ Отклонить", "callback_data": f"reject:{booking_id}"},
        ]]
    }


def send_telegram(chat_ids: list[str], text: str, reply_markup: dict | None = None) -> None:
    """Вызывается в фоне (BackgroundTasks). Без токена бота — только лог."""
    if not settings.telegram_bot_token:
        log.info("telegram (не настроен) → %s: %s", chat_ids, text)
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    for chat_id in chat_ids:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            httpx.post(url, json=payload, timeout=5).raise_for_status()
        except httpx.HTTPError:
            log.exception("Не удалось отправить сообщение в Telegram chat_id=%s", chat_id)


def answer_callback(callback_id: str, text: str) -> None:
    if not settings.telegram_bot_token:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": text},
            timeout=5,
        )
    except httpx.HTTPError:
        log.exception("answerCallbackQuery failed")


def describe(booking: Booking) -> str:
    tz = settings.tz
    s = booking.start_at.astimezone(tz).strftime("%d.%m")
    e = booking.end_at.astimezone(tz).strftime("%d.%m")
    guest = booking.guest.name if booking.guest else "—"
    return f"«{booking.apartment.title}», {s}–{e}, гость {guest}, {booking.total_price:.0f} сом"
