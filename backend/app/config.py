"""Настройки приложения. Всё берётся из переменных окружения (см. .env.example)."""
import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/konok")
    )
    secret_key: str = field(default_factory=lambda: _env("SECRET_KEY", "dev-secret-change-me"))
    token_ttl_hours: int = field(default_factory=lambda: int(_env("TOKEN_TTL_HOURS", "72")))
    # Сколько минут даты держатся за гостем, пока он не загрузит чек (ТЗ 3.2.3)
    hold_minutes: int = field(default_factory=lambda: int(_env("HOLD_MINUTES", "30")))
    media_dir: str = field(default_factory=lambda: _env("MEDIA_DIR", "./media"))
    max_upload_mb: int = 10
    max_photos_per_apartment: int = 20
    max_apartments_per_account: int = 50
    telegram_bot_token: str | None = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN") or None)
    telegram_webhook_secret: str = field(
        default_factory=lambda: _env("TELEGRAM_WEBHOOK_SECRET", "dev-webhook-secret")
    )
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL", "http://localhost:5173"))
    tz_name: str = field(default_factory=lambda: _env("TZ_NAME", "Asia/Bishkek"))
    expire_interval_seconds: int = field(default_factory=lambda: int(_env("EXPIRE_INTERVAL_SECONDS", "30")))

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.tz_name)


settings = Settings()
