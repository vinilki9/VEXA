# VEXA Backend — FastAPI / PostgreSQL

Текущие исходники: VEXA 0.3.5. Этот репозиторий **не утверждает**, что сервер или полный цикл заказа работают в production.

## Установка зависимостей и тесты

```bash
python -m venv .venv
# Активируйте виртуальное окружение (PowerShell: .venv\Scripts\Activate.ps1)
python -m pip install -r requirements.txt
PYTHONPATH=. python -m pytest -q tests
```

Для production используйте Docker-конфигурацию и миграции из `../infrastructure/compose.production.yml`, инструкцию `../docs/PRODUCTION_DEPLOYMENT_0.3.5.md`. Для локального сервера Windows 11 — `../README_LOCAL_SETUP.md`. Не запускайте публично сервер с SQLite или стандартным `SECRET_KEY`.

## Пользователи

Паролей по умолчанию **нет**. После миграций создать раздельные учётные записи с надёжными паролями через CLI (команды внутри API-контейнера):

```bash
python -m app.create_admin --username dispatcher1 --role dispatcher --branch-id <UUID_ТАКСОПАРКА>
python -m app.create_platform_admin --username platform_admin1
```

Обе команды запрашивают пароль **интерактивно**, без отображения в истории команд. Не отправляйте реальные пароли в чат или Git.

## Основные API

- `POST /api/v1/dispatch/auth/login`, `GET /api/v1/dispatch/auth/me`;
- `POST /api/v1/platform-admin/auth/login`, `GET /api/v1/platform-admin/auth/me`;
- `POST /api/v1/driver/auth/login`, `POST /api/v1/driver/orders/{order_id}/status`;
- `GET /api/v1/passenger/orders/{order_identifier}`;
- `GET /health` — проверяет соединение с БД.

Swagger `/docs` и `/openapi.json` доступны только в development, в production выключены. Реальный запуск и тестирование авторизации/БД остаются необходимыми.
