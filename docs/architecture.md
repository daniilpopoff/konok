# Konok — архитектура (v0.1, 07.11.2026)

## Как устроено

```
Гость (телефон) ──► Витрина / страница брони (React) ──┐
Владелец, менеджер ─► CRM (React) ─────────────────────┤  REST /api, JSON UTF-8
Telegram ─► webhook /api/telegram/webhook ─────────────┤
                                                       ▼
                                   FastAPI (backend/app)
                                     ├─ routers/   — HTTP-слой, проверка прав
                                     ├─ services/  — бизнес-логика (брони, аналитика, уведомления, файлы)
                                     └─ models.py  — SQLAlchemy 2.0
                                                       ▼
                         PostgreSQL 16 (+ btree_gist)   ·   диск: media/public (фото, QR), media/private (чеки)
```

Фронт (Белек) и бэк (Даниил) договариваются только через контракт API ниже: Swagger сам строится на `/docs`.

## Главные решения

| Решение | Почему |
|---|---|
| Защита от двойной брони — `EXCLUDE USING gist (apartment_id WITH =, tstzrange(start_at, end_at) WITH &&)` | Проверяет сама база, работает при одновременных запросах. Тест: 50 параллельных попыток → ровно 1 успех |
| Бронь хранит дату **и время** (`timestamptz`) | Заезд 14:00 / выезд 12:00 → брони «стык в стык» не конфликтуют; почасовая аренда добавится без смены модели |
| Блокировка дат = бронь со статусом `blocked` | Одно ограничение базы защищает и брони, и блокировки |
| Все переходы статусов — через `services/booking.transition()` | Недопустимый переход → 409, каждый шаг пишется в `booking_events` |
| Неоплаченные брони снимаются фоновым циклом (30 с) + перед каждой новой бронью | Даты освобождаются сами, даже если никто не заходит |
| Tenant = `accounts`, у всех данных `account_id`; чужое отдаём как 404 | Изоляция владельцев проверяется сервером (ТЗ 3.1.2) |
| Чеки — в `media/private`, отдаются только через `/api/bookings/{id}/receipt` с проверкой прав | Чек не утекает по прямой ссылке |
| Telegram — `BackgroundTasks`, ошибки только в лог | Сбой бота не ломает CRM (ТЗ 3.6.1) |
| Кнопка в боте идемпотентна | Повторное нажатие не меняет статус второй раз |

## Статусы брони

```
awaiting_payment ──чек──► awaiting_confirmation ──подтвердить──► confirmed ──► checked_in ──► checked_out ──► closed
     │  ▲                         │                                  │
     │  └────────отклонить────────┘                                  │
     ├──30 мин без чека──► expired                                   │
     └───────────────отмена (гость/менеджер)──────► cancelled ◄──────┘
blocked ──снять──► cancelled
```

## Таблицы

| Таблица | Что хранит |
|---|---|
| accounts | Бизнес владельца: логин витрины, реквизиты, QR |
| users | Владелец / менеджер / админ, Telegram chat_id |
| apartments | Квартира: цены, правила, предоплата, залог, срок бесплатной отмены |
| apartment_photos, price_overrides | Фото, особые цены на даты |
| guests | Гость в рамках владельца (уникален по телефону), заметки, чёрный список |
| bookings | Брони и блокировки, деньги, залог, источник, токен гостя |
| booking_events | История статусов: кто и когда |
| reviews | Один отзыв на завершённую бронь + ответ владельца |
| expenses | Расходы по квартире |
| notifications | Лента событий внутри CRM |

## Контракт API (52 метода)

Публичные (без входа) — `/api/public/...`; остальное — `Authorization: Bearer <token>`.

| Метод | Путь | Что делает |
|---|---|---|
| POST | `/api/auth/register` | Регистрация владельца (создаёт аккаунт и логин витрины) |
| POST | `/api/auth/login` | Вход, выдаёт JWT |
| GET | `/api/auth/me` | Текущий пользователь |
| POST / GET | `/api/team/managers`, `/api/team` | Добавить менеджера / список команды (владелец) |
| PATCH | `/api/settings` | Название, реквизиты (владелец) |
| POST | `/api/settings/payment-qr` | Загрузить QR для оплаты |
| POST | `/api/telegram/link-code` | Код для привязки Telegram |
| GET / POST | `/api/apartments` | Список / создать квартиру |
| GET / PATCH | `/api/apartments/{id}` | Карточка / изменить |
| POST / DELETE | `/api/apartments/{id}/photos[/{photo_id}]` | Фото (до 20, до 10 МБ) |
| PUT | `/api/apartments/{id}/prices` | Особая цена на дату |
| GET | `/api/bookings` | Список с фильтрами: status, apartment_id, source, даты, поиск q |
| POST | `/api/bookings` | Ручная бронь (звонок, WhatsApp) |
| GET | `/api/bookings/calendar?date_from&date_to` | Данные шахматки |
| POST | `/api/bookings/blocks` | Заблокировать даты |
| GET | `/api/bookings/{id}` | Карточка брони + история + ссылка гостя |
| GET | `/api/bookings/{id}/receipt` | Файл чека |
| POST | `/api/bookings/{id}/confirm` · `reject` | Подтвердить / отклонить оплату |
| POST | `/api/bookings/{id}/check-in` · `check-out` | Заселение (остаток, залог) / выезд |
| POST | `/api/bookings/{id}/deposit` | Залог: вернуть / удержать с причиной |
| POST | `/api/bookings/{id}/close` · `cancel` · `refunded` | Закрыть / отменить / отметить возврат |
| GET | `/api/bookings/{id}/whatsapp` | Ссылка wa.me с готовым текстом |
| GET / PATCH | `/api/guests`, `/api/guests/{id}` | База гостей, заметки, чёрный список |
| POST | `/api/reviews/{id}/reply` | Ответ владельца на отзыв |
| GET / POST / DELETE | `/api/expenses` | Расходы (владелец) |
| GET | `/api/analytics?date_from&date_to` | Загрузка, выручка, прибыль, источники (владелец) |
| GET | `/api/export/bookings.csv` | Выгрузка для Excel |
| GET / POST | `/api/notifications`, `/read-all` | Лента событий |
| GET | `/api/public/{slug}` | Витрина владельца |
| GET | `/api/public/{slug}/{apt}` | Страница квартиры: фото, отзывы, занятые даты |
| POST | `/api/public/{slug}/{apt}/quote` | Расчёт стоимости |
| POST | `/api/public/{slug}/{apt}/bookings` | Бронь гостя |
| GET | `/api/public/b/{token}` | Страница брони гостя |
| POST | `/api/public/b/{token}/receipt` · `cancel` · `review` | Чек / отмена / отзыв |
| POST | `/api/telegram/webhook` | Вебхук бота (секрет в заголовке) |
| POST | `/api/admin/accounts/{id}/block` | Блокировка аккаунта (админ платформы) |

## Что дальше по бэкенду

1. Alembic-миграции вместо `create_all` (ТЗ 4.2).
2. Ресайз фото и превью.
3. Напоминания бота за сутки до заезда и в день выезда (cron-задача).
4. Нагрузочный тест по ТЗ 6.3 (locust).
