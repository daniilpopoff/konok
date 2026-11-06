from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=20, max_overflow=40)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Создаёт расширение и таблицы. На следующем спринте заменяем на миграции Alembic."""
    from . import models  # noqa: F401  — регистрирует модели

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
