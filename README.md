# Konok — CRM для посуточной аренды

Рантье заводит квартиры → кидает ссылку в Lalafo / Instagram → гость сам бронирует и прикладывает чек →
рантье подтверждает в Telegram одной кнопкой. ВКР: Попов Д. (бэкенд), Корчуев Б. (фронтенд).

## Запуск за 2 минуты

```bash
cp .env.example .env          # впишите SECRET_KEY
docker compose up --build     # API на http://localhost:8000, Swagger — /docs
docker compose exec backend python seed.py   # демо: azamat@konok.kg / password123
```

## Без Docker (для разработки)

```bash
cd backend
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/konok
uvicorn app.main:app --reload
```

## Тесты

```bash
createdb konok_test
cd backend && DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/konok_test pytest -q
```

21 тест: сквозной сценарий брони, 50 параллельных броней, истечение неоплаченной брони, отклонение чека,
правила отмены, цены на выходные, изоляция владельцев, права менеджера, приватность чеков,
идемпотентность Telegram-кнопок, точность аналитики.

## Где что

- `backend/app/services/booking.py` — вся логика броней и статусов
- `backend/app/models.py` — модель данных + ограничение против двойных броней
- `docs/architecture.md` — архитектура, решения, контракт API
