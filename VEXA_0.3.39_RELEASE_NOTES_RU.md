# VEXA Ecosystem Legal 0.3.39

Исходная база: VEXA 0.3.38.

## Реально изменённые файлы
- backend/app/legal_acceptance_models.py — модель журнала принятых версий.
- backend/app/legal_acceptance_service.py — проверка текущих обязательных версий, фиксация подтверждений.
- backend/app/legal_account_api.py — авторизованные endpoints истории и подтверждений для client/driver/dispatcher/admin.
- backend/app/passenger_auth.py — запись подтверждений после SMS-верификации.
- backend/app/main.py — подключение API.
- backend/migrations/versions/0020_legal_acceptance_history.py — миграция PostgreSQL.
- backend/tests/test_legal_acceptance_service.py — новые тесты.
- docs/VEXA_LEGAL_0.3.39_INTEGRATION_RU.md — технические и юридические ограничения.

## Проверки
31 тест Python прошёл локально. Компиляция изменённых Python-модулей прошла. Android APK и полные интеграционные тесты PostgreSQL не выполнялись.

**Нельзя включать в production, пока юридические тексты остаются черновиками.**
