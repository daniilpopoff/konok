"""Вебхук Telegram-бота: привязка чата и кнопки «Подтвердить / Отклонить» (ТЗ 3.5.4)."""
import hmac

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Booking, BookingStatus as S, Role, User
from ..services import booking as svc
from ..services import notify

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def webhook(request: Request, bg: BackgroundTasks, db: Session = Depends(get_db),
                  x_telegram_bot_api_secret_token: str | None = Header(default=None)):
    if not hmac.compare_digest(x_telegram_bot_api_secret_token or "", settings.telegram_webhook_secret):
        raise HTTPException(403, "bad secret")
    update = await request.json()

    msg = update.get("message") or {}
    text = (msg.get("text") or "").strip()
    if text.startswith("/start"):
        chat_id = str(msg.get("chat", {}).get("id"))
        code = text.removeprefix("/start").strip()
        user = db.scalar(select(User).where(User.telegram_link_code == code)) if code else None
        if user:
            user.telegram_chat_id, user.telegram_link_code = chat_id, None
            db.commit()
            bg.add_task(notify.send_telegram, [chat_id], f"Готово, {user.name}! Сюда будут приходить брони и чеки.")
        else:
            bg.add_task(notify.send_telegram, [chat_id], "Код не найден. Возьмите новый в настройках Konok.")
        return {"ok": True}

    cq = update.get("callback_query")
    if not cq:
        return {"ok": True}
    callback_id = cq.get("id", "")
    chat_id = str(cq.get("from", {}).get("id"))
    action, _, raw_id = (cq.get("data") or "").partition(":")
    user = db.scalar(select(User).where(User.telegram_chat_id == chat_id,
                                        User.role.in_([Role.OWNER.value, Role.MANAGER.value])))
    booking = db.get(Booking, int(raw_id)) if raw_id.isdigit() else None
    if user is None or booking is None or booking.account_id != user.account_id:
        bg.add_task(notify.answer_callback, callback_id, "Нет доступа к этой брони")
        return {"ok": True}

    actor = f"{user.name} ({user.role}, Telegram)"
    try:
        if action == "confirm":
            changed = svc.confirm_payment(db, booking, actor)
            reply = "Предоплата подтверждена ✅" if changed else "Уже подтверждено"
        elif action == "reject":
            if booking.status != S.AWAITING_CONFIRMATION.value:
                reply = "Эта бронь уже обработана"
            else:
                svc.reject_payment(db, booking, "Отклонено в Telegram", actor)
                reply = "Чек отклонён, гостю откроется повторная оплата"
        else:
            reply = "Неизвестное действие"
        db.commit()
    except svc.BookingError as e:
        db.rollback()
        reply = e.detail
    bg.add_task(notify.answer_callback, callback_id, reply)
    return {"ok": True}
