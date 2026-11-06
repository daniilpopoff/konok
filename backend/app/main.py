import asyncio
import contextlib
import logging
import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal, get_db, init_db
from .models import Account, User
from .routers import apartments, auth, bookings, crm, public, telegram
from .security import admin_only
from .services.booking import BookingError, expire_stale

log = logging.getLogger("konok")


async def _expire_loop() -> None:
    """Каждые N секунд снимаем неоплаченные брони, чтобы даты освобождались сами."""
    while True:
        await asyncio.sleep(settings.expire_interval_seconds)
        try:
            with SessionLocal() as db:
                n = expire_stale(db)
                db.commit()
                if n:
                    log.info("expired %s bookings", n)
        except Exception:  # фоновая задача не должна падать навсегда
            log.exception("expire loop failed")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    os.makedirs(os.path.join(settings.media_dir, "public"), exist_ok=True)
    task = asyncio.create_task(_expire_loop())
    yield
    task.cancel()


app = FastAPI(title="Konok API", version="0.1.0", lifespan=lifespan,
              description="CRM для посуточной аренды квартир")
app.add_middleware(CORSMiddleware, allow_origins=[settings.public_base_url], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(BookingError)
async def booking_error_handler(_: Request, exc: BookingError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


for r in (auth.router, apartments.router, bookings.router, crm.router, public.router, telegram.router):
    app.include_router(r, prefix="/api")

os.makedirs(os.path.join(settings.media_dir, "public"), exist_ok=True)
# Публично отдаём только фото и QR; чеки — через /api/bookings/{id}/receipt с проверкой прав
app.mount("/media/public", StaticFiles(directory=os.path.join(settings.media_dir, "public")), name="media")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/admin/accounts/{account_id}/block")
def block_account(account_id: int, blocked: bool = True, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    acc = db.get(Account, account_id)
    if acc is None:
        raise HTTPException(404, "Аккаунт не найден")
    acc.is_blocked = blocked
    db.commit()
    return {"id": acc.id, "is_blocked": acc.is_blocked}
