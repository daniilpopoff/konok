"""Хранение загруженных файлов на диске сервера (фото квартир, чеки, QR)."""
import os
import uuid

from fastapi import UploadFile

from ..config import settings
from .booking import BookingError

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
RECEIPT_EXT = IMAGE_EXT | {".pdf"}
# Сигнатуры файлов: проверяем содержимое, а не только расширение
MAGIC = {
    ".jpg": [b"\xff\xd8\xff"], ".jpeg": [b"\xff\xd8\xff"], ".png": [b"\x89PNG"],
    ".webp": [b"RIFF"], ".pdf": [b"%PDF"],
}


def save_upload(file: UploadFile, folder: str, allowed: set[str]) -> str:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise BookingError(422, f"Формат не поддерживается. Можно: {', '.join(sorted(allowed))}")
    limit = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise BookingError(413, f"Файл больше {settings.max_upload_mb} МБ")
    if not any(data.startswith(sig) for sig in MAGIC[ext]):
        raise BookingError(422, "Содержимое файла не совпадает с расширением")
    rel = f"{folder}/{uuid.uuid4().hex}{ext}"
    abs_path = os.path.join(settings.media_dir, rel)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as fh:
        fh.write(data)
    return rel


def abs_path(rel: str) -> str:
    full = os.path.realpath(os.path.join(settings.media_dir, rel))
    root = os.path.realpath(settings.media_dir)
    if not full.startswith(root + os.sep):
        raise BookingError(404, "Файл не найден")
    return full
