import secrets

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Account, Role, User
from ..schemas import AccountSettingsIn, LoginIn, ManagerIn, RegisterIn, TokenOut, UserOut
from ..security import create_token, get_current_user, hash_password, owner_only, verify_password
from ..services.files import IMAGE_EXT, save_upload

router = APIRouter(tags=["auth"])

RESERVED_SLUGS = {"api", "admin", "b", "app", "login", "register", "media", "static", "konok"}


def user_out(u: User) -> UserOut:
    return UserOut(id=u.id, email=u.email, name=u.name, role=u.role, account_id=u.account_id,
                   account_slug=u.account.slug if u.account else None,
                   account_name=u.account.name if u.account else None,
                   telegram_linked=u.telegram_chat_id is not None)


@router.post("/auth/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if data.slug in RESERVED_SLUGS or db.scalar(select(Account).where(Account.slug == data.slug)):
        raise HTTPException(409, "Этот логин уже занят")
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Пользователь с таким email уже есть")
    account = Account(slug=data.slug, name=data.business_name)
    user = User(account=account, email=data.email.lower(), password_hash=hash_password(data.password),
                name=data.name, role=Role.OWNER.value)
    db.add_all([account, user])
    db.commit()
    return TokenOut(access_token=create_token(user.id))


@router.post("/auth/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Неверный email или пароль")
    return TokenOut(access_token=create_token(user.id))


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.post("/team/managers", response_model=UserOut, status_code=201)
def add_manager(data: ManagerIn, owner: User = Depends(owner_only), db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Пользователь с таким email уже есть")
    m = User(account_id=owner.account_id, email=data.email.lower(), password_hash=hash_password(data.password),
             name=data.name, role=Role.MANAGER.value)
    db.add(m)
    db.commit()
    return user_out(m)


@router.get("/team", response_model=list[UserOut])
def team(owner: User = Depends(owner_only), db: Session = Depends(get_db)):
    return [user_out(u) for u in db.scalars(select(User).where(User.account_id == owner.account_id))]


@router.get("/settings")
def get_settings(owner: User = Depends(owner_only)):
    acc = owner.account
    return {"name": acc.name, "slug": acc.slug, "payment_details": acc.payment_details,
            "payment_qr": acc.payment_qr_path}


@router.patch("/settings")
def update_settings(data: AccountSettingsIn, owner: User = Depends(owner_only), db: Session = Depends(get_db)):
    acc = owner.account
    if data.name is not None:
        acc.name = data.name
    if data.payment_details is not None:
        acc.payment_details = data.payment_details
    db.commit()
    return {"name": acc.name, "slug": acc.slug, "payment_details": acc.payment_details,
            "payment_qr": acc.payment_qr_path}


@router.post("/settings/payment-qr")
def upload_qr(file: UploadFile = File(...), owner: User = Depends(owner_only), db: Session = Depends(get_db)):
    owner.account.payment_qr_path = save_upload(file, "public/qr", IMAGE_EXT)
    db.commit()
    return {"payment_qr": owner.account.payment_qr_path}


@router.post("/telegram/link-code")
def telegram_link_code(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Код для привязки: пользователь пишет боту /start <код>."""
    user.telegram_link_code = secrets.token_hex(4)
    db.commit()
    return {"code": user.telegram_link_code, "instruction": f"Отправьте боту: /start {user.telegram_link_code}"}
