VEXA 0.3.41 VPS — актуальный запуск: VPS_START_HERE.md (в корне).
Публичный адрес: https://45.143.139.162. Нижеследующие инструкции относятся к прежним версиям или локальному режиму.

**VEXA MAP 0.3.17:** Отображение локальных растровых MBTiles внутри Client и Driver; инструкция: [`VEXA_MAP/ANDROID_OFFLINE_RENDER_0.3.17.md`](VEXA_MAP/ANDROID_OFFLINE_RENDER_0.3.17.md). Векторные PBF, офлайн-адреса и маршруты ещё не готовы.

# VEXA Taxi + VEXA MAP — исходный проект 0.3.16 (Android Offline Manager)

**Обновление интерфейсов 0.3.14:** Client, Driver, Dispatcher, Platform Admin и VEXA MAP используют утверждённую палитру — графитовый фон, приглушённую бирюзу и яркую линию маршрута. Подробности: `design/VEXA_DESIGN_GUIDE_RU.md` и `RELEASE_REPORT_0.3.14.md`. Схемы тарифов, авторизации и заказов этим обновлением не изменялись.

**Текущая конфигурация:** локальная разработка на Windows 11 (установка отложена) и **отдельно** подготовленный сценарий переноса на будущий Linux-сервер с HTTPS. Этот архив — исходный код, не развёрнутая система.

## Состав

- `android/client/` — приложение пассажира (Android / Kotlin).
- `android/driver/` — приложение водителя (Android / Kotlin).
- `backend/` — FastAPI, PostgreSQL, авторизация, заказы, тарифы.
- `dispatcher/` — веб-панель диспетчера.
- `platform-admin/` — отдельная веб-панель главного администратора.
- `VEXA_MAP/` — локальный сервис карт, поиск адресов, подключение OSRM; данные карт не включены.
- `infrastructure/` — локальный Compose и **отдельный** production Compose с HTTPS Caddy.
- `tools/` — PowerShell-скрипты подготовки LAN IP и проверок.

## С чего начинать

1. Прочитайте `START_HERE.txt`, `RELEASE_REPORT_0.3.5.md` и `docs/FEATURE_READINESS_0.3.5.md`.
2. Когда будет удобно настраивать Windows 11, используйте `README_LOCAL_SETUP.md`. Не требуется отдельно ставить PostgreSQL на Windows: он запускается контейнером.
3. Перед тестированием в LAN настройте новый `.env` из `.env.example`, установите собственные сильные секреты, выполните подготовку IP. Реальный `.env` никогда не сохраняйте в Git и не прикладывайте к обращениям за помощью.
4. Реальные файлы MBTiles, адресный индекс и граф OSRM нужно загрузить отдельно; без них сервер карт не сможет отобразить полноценную карту или построить маршрут.
5. Для будущего Linux-сервера используйте **только** `docs/PRODUCTION_DEPLOYMENT_0.3.5.md`; не публикуйте локальные порты Docker в интернет. HTTPS-адреса Android Release задаются через Gradle.

## Авторизация и маршруты

- Диспетчер: `POST /api/v1/dispatch/auth/login`; проверка профиля — `GET /api/v1/dispatch/auth/me`.
- Главный администратор: `POST /api/v1/platform-admin/auth/login`; проверка — `GET /api/v1/platform-admin/auth/me`.
- Водитель: `POST /api/v1/driver/auth/login`; статус поездки — `POST /api/v1/driver/orders/{order_id}/status`.
- Пассажир: `GET /api/v1/passenger/orders/{order_identifier}` с собственным Bearer-токеном.

Все маршруты, кроме входа, требуют соответствующих прав. В 0.3.5 токены диспетчера без поля `token_type=dispatcher` больше не принимаются: после обновления потребуется повторная авторизация. Универсальных логинов или паролей по умолчанию нет.

## Доступные тесты исходников

Из корня проекта при наличии Python + test dependencies:

```bash
PYTHONPATH=backend python -m pytest -q backend/tests/test_admin_portal_contract.py backend/tests/test_mobile_integration_contract.py backend/tests/test_driver_status_retry_contract.py backend/tests/test_routing_providers.py backend/tests/test_routing.py backend/tests/test_route_pricing.py backend/tests/test_pricing.py backend/tests/test_order_fare_breakdown_migration.py backend/tests/test_remove_anonymous_order_migration.py
python -m unittest discover -s VEXA_MAP/tests -v
```

Для **всего** набора тестов Backend требуются зависимости из `backend/requirements.txt`, включая `python-jose[cryptography]`, а для настоящей интеграционной проверки — локальный PostgreSQL/Docker. Android APK, сборки React/Vite и входы на работающем локальном сервере в данном выпуске не проверены.


### VEXA MAP 0.3.15
Добавлен каталог региональных офлайн-пакетов и потоковая выдача с докачкой. Детали и ограничения: `VEXA_MAP/RELEASE_0.3.15.md`.

### VEXA MAP Android Offline Manager 0.3.16
В Client и Driver добавлено управление скачиваемыми картами восьми федеральных округов. Общая библиотека: `android/shared/vexa-map-offline/`. Многогигабайтные карты не входят в архив; скачивание заработает только после публикации реальных пакетов на VEXA MAP. Это пока не офлайн-рендеринг и не офлайн-навигация. Подробнее: `VEXA_MAP/ANDROID_OFFLINE_MANAGER_0.3.16.md`.
