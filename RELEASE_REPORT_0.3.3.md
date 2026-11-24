# VEXA Taxi / VEXA MAP — локальные панели 0.3.3

Дата: 21 ноября 2026. Основа: `VEXA_CLIENT_DRIVER_BACKEND_COMPAT_0.3.2.zip`.

## Исправления

- Исправлены пути статических ресурсов двух веб-панелей: относительный Vite `base: './'` работает при запуске на отдельных портах (`:8081/`, `:8082/`) и через внешний Nginx по префиксам `/dispatch/`, `/platform-admin/` при удалении префикса через `proxy_pass`.
- Диспетчерская больше не показывает рабочую панель на основании лишь сохранённого токена: сначала запрашивает `/api/v1/dispatch/auth/me`, затем загружает заказы и водителей. Неудачная загрузка заказов не должна автоматически стирать действительную сессию.
- Backend получил `GET /api/v1/platform-admin/auth/me` с обязательной платформенной ролью и профилем авторизованного администратора. Админка проверяет сессию через этот endpoint, а не через список организаций, и показывает фактический логин.
- Добавлен скрипт `tools/check_admin_portals.ps1`, проверяющий HTML страниц и что собранные JS-файлы возвращаются именно как JavaScript, а не как HTML fallback.
- Добавлены 5 тестов исходных контрактов веб-панелей и авторизации, уточнён `README_LOCAL_SETUP.md`.

## Проверки в среде подготовки

- `PYTHONPATH=. pytest -q tests/test_admin_portal_contract.py tests/test_mobile_integration_contract.py tests/test_pricing.py tests/test_routing.py tests/test_routing_providers.py tests/test_route_pricing.py` (из `backend/`): **52 теста пройдены**, дополнительно **14 subtests**.
- `python -m unittest discover -s VEXA_MAP/tests -v`: **11 тестов пройдены**. В ходе тестов возникали ResourceWarning об освобождении SQLite-соединений, итог тестов OK.
- `python -m compileall -q backend/app/platform_admin_auth.py`: пройдено.
- Компиляция веб-панелей (`npm run build`) **не подтверждена**: зависимости npm не удалось получить в текущей среде. В репозитории нет node_modules, браузерные тесты и настоящая аутентификация не выполнены.
- Docker, PostgreSQL, Windows локальный компьютер, Android сборки и реальные MBTiles/OSRM **не тестировались**.

## Как проверить на Windows

1. Распаковать архив; настроить локальные `.env` и IP по `README_LOCAL_SETUP.md`.
2. Запустить `docker compose -f infrastructure/docker-compose.yml up -d --build` (доступ к npm-реестру требуется для сборки веб-панелей).
3. Из корня `VEXA-deploy` выполнить: `powershell -ExecutionPolicy Bypass -File .\tools\check_admin_portals.ps1`.
4. Открыть `http://127.0.0.1:8081/` и `http://127.0.0.1:8082/`. Для полноценного входа заранее нужны локальные пользователи с активными `DispatcherProfile` и `PlatformAdmin` и запущенная БД. В проекте нет паролей по умолчанию.
5. После запуска проверить `/api/v1/dispatch/auth/me` и `/api/v1/platform-admin/auth/me` с соответствующими Bearer-токенами; проверить отказ при неверном токене или роли.

**Ограничение:** наличие исправленного кода не означает, что панели прямо сейчас работают на компьютере пользователя. До запуска и реального входа это подготовленная версия исходников, не подтверждённая инсталляция.

GitHub, VPS, сервер пользователя и исходный ZIP не изменялись.
