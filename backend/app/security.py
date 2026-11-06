from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Role, User

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.token_ttl_hours)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.secret_key, algorithm="HS256")


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Нужна авторизация")
    try:
        payload = jwt.decode(creds.credentials, settings.secret_key, algorithms=["HS256"])
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        user = None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный токен")
    if user.account is not None and user.account.is_blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Аккаунт заблокирован")
    return user


def require(*roles: Role):
    """Зависимость: пускает только указанные роли. Права проверяет сервер (ТЗ 3.1.2)."""
    allowed = {r.value for r in roles}

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостаточно прав")
        return user

    return checker


staff = require(Role.OWNER, Role.MANAGER)
owner_only = require(Role.OWNER)
admin_only = require(Role.ADMIN)
