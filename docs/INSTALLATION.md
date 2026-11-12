# Локальная установка и запуск

## Backend
1. Установить Python 3.11+.
2. Перейти в `backend`, создать виртуальное окружение.
3. `pip install -r requirements.txt`.
4. `uvicorn app.main:app --reload`.
5. Проверить `/health` и `/docs`.

## Dispatcher
1. Установить Node.js 20+.
2. Перейти в `dispatcher`.
3. `npm install`.
4. `npm run dev`.

## PostgreSQL / Redis
Из каталога `infrastructure`: `docker compose up -d db redis`.
Перед использованием задайте секреты из `.env.example`. Примерные значения не подходят для production.

## Android
Открыть каждый проект отдельно в Android Studio. Инструкции в `ANDROID_BUILD.md`.

## VPS
Эта инструкция не выполняет подключение к VPS. Сервер не проверялся и не изменялся. Развёртывание возможно только после отдельного согласования и production hardening.
