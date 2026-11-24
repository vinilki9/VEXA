# VEXA — проверка системы, этап 3

## Подтверждено
- Архив этапа 2 распакован; подготовлена новая копия.
- Driver: адрес стиля VEXA MAP теперь можно задавать через Gradle property `vexaMapStyleUrl` (например, в локальном `gradle.properties`, без секретных ключей). По умолчанию URL пустой и карта не загрузится.
- Backend: выполнен `python -m pytest -q`; тесты остановились на сборе с тремя ошибками `ModuleNotFoundError: No module named 'jose'`.
- `python-jose[cryptography]==3.3.0` уже присутствует в `backend/requirements.txt`. Это отсутствие зависимости в среде проверки, а не доказанная ошибка кода Backend.

## Не подтверждено
- Доступность VPS, Docker, PostgreSQL, API, авторизация и живые заказы.
- Gradle сборка Client и Driver; TypeScript/Vite сборка Dispatcher.
- Работа MapLibre на Android и наличие реального сервера тайлов.
- Полная замена 2ГИС: Client всё ещё зависит от него.

## Дальнейшие проверки
1. Установить зависимости Backend в изолированное окружение и повторить pytest.
2. Проверить `npm ci && npm run build` для Dispatcher.
3. Проверить `gradlew assembleDebug` отдельно для Client и Driver.
4. Подключить тестовый сервер стилей/тайлов и проверить Android на устройстве.
5. Только после подтверждения эквивалентной функциональности заменить 2ГИС в Client.

Ни VPS, ни GitHub не изменялись.
