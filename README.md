# Konok — CRM для посуточной аренды

Рантье заводит квартиры → кидает ссылку в Lalafo / Instagram → гость сам бронирует и прикладывает чек →
рантье подтверждает оплату в CRM или в Telegram одной кнопкой. ВКР: Попов Д., Корчуев Б.

## Запуск (нужен только Docker Desktop)

```bash
cp .env.example .env                                  # один раз; впишите SECRET_KEY
docker compose up --build                             # первый раз 2–3 минуты
docker compose exec backend python seed.py            # демо-данные, один раз на чистой базе
```

| Что | Адрес |
|---|---|
| Сайт: главная, вход, CRM | http://localhost:5173 |
| Демо-витрина для гостей | http://localhost:5173/azamat |
| Вход владельца | azamat@konok.kg / password123 |
| Вход менеджера | aigul@konok.kg / password123 |
| API и Swagger | http://localhost:8000/docs |

Остановить — `Ctrl+C`, данные сохраняются. Начать с чистой базы — `docker compose down -v`.

## Что есть во фронте

- **Гость:** витрина владельца, страница квартиры с календарём свободных дат и расчётом цены, бронь без регистрации,
  страница брони (оплата по QR, загрузка чека, таймер 30 минут, отмена, адрес после подтверждения, отзыв).
- **CRM:** шахматка с полосами броней и карточкой брони (подтвердить/отклонить чек, заселить, выезд, залог, закрыть,
  отменить, WhatsApp), список броней с фильтрами, квартиры с фото и ссылками для Lalafo/Instagram, гости и чёрный список,
  отзывы с ответами, аналитика, расходы, настройки (реквизиты, QR, Telegram, менеджеры).

## Тесты

```bash
docker compose exec db createdb -U konok konok_test   # один раз
docker compose exec backend pytest -q                 # 21 тест, идут только в konok_test
cd frontend && npm install && npm run typecheck       # проверка типов фронта
```

## Где что

- `backend/app/services/booking.py` — вся логика броней и статусов
- `backend/app/models.py` — модель данных + ограничение против двойных броней
- `frontend/src/pages/guest` — витрина, квартира, страница брони
- `frontend/src/pages/app` — CRM
- `docs/` — ТЗ, PRD, архитектура и API
