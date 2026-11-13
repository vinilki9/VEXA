# VEXA Backend — стартовый серверный каркас

Стек: FastAPI, SQLAlchemy 2, PostgreSQL, JWT, bcrypt.
Первый пилот: Оболенск (`city_id=obolensk`). Архитектура поддерживает несколько городов.

## Запуск локально
1. Установить Python 3.11+.
2. Создать виртуальное окружение и установить зависимости:
   `python -m venv .venv`
   `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)
   `pip install -r requirements.txt`
3. Скопировать `.env.example` в `.env`, задать `SECRET_KEY` и `DATABASE_URL`.
4. Создать первого диспетчера:
   `python -m app.create_admin --username dispatcher --password 'qwerty'`
5. Запустить:
   `uvicorn app.main:app --host 0.0.0.0 --port 8000`
6. Документация API: `/docs`; проверка: `/health`.

По умолчанию используется SQLite для локального ознакомления. Для сервера укажи PostgreSQL в `DATABASE_URL`, например:
`postgresql+psycopg://vexa_user:strong_password@127.0.0.1:5432/vexa`

## Основные маршруты
- `POST /api/dispatcher/auth/login`
- `GET /api/dispatcher/auth/me`
- `GET /api/dispatcher/orders`
- `POST /api/dispatcher/orders`
- `PATCH /api/dispatcher/orders/{order_id}/status`
- `GET /api/dispatcher/summary`

Все маршруты диспетчера, кроме login, требуют `Authorization: Bearer <token>`.

## Важно перед боевым запуском
Это стартовый каркас, а не готовая production-система. Перед публикацией необходимо:
- подключить PostgreSQL и миграции Alembic;
- настроить HTTPS на принадлежащем вам VPS через Nginx;
- задать длинный случайный `SECRET_KEY`, закрыть публичный доступ к БД;
- добавить rate limiting, аудит действий, резервное копирование и мониторинг;
- реализовать проверку допустимых переходов статусов, распределение водителей,
  платежи, тарифы, уведомления и интеграционные тесты;
- не использовать тестовые пароли и не публиковать `.env`.
