# VEXA 0.3.41 — отчёт VPS edition

Исходный архив: VEXA_INTEGRATION_AUDIT_STAGE1_0.3.41_SOURCE.zip. Внешний URL: https://45.143.139.162. Все файлы исходного архива сохранены, бизнес-функции не заменены. Исторические отчёты и внутренние адреса сохранены. Android versionName/versionCode исходной сборки не изменены (0.3.19/19); название 0.3.41 относится к пакету исходников.

Изменены Gradle-конфиги обоих приложений, production Compose/Caddy, публичный URL backend, шаблон окружения, инструкция и автодеплой. Восстановлены Gradle Wrapper JAR из 0.3.42 с совпадающей конфигурацией 8.13; обе JAR содержат GradleWrapperMain.class. Для PostgreSQL внесено расширение alembic_version.version_num до VARCHAR(128), чтобы поддержать длинные идентификаторы миграций; реальный PostgreSQL не тестировался. Web-панели сохранены на same-origin API. Прямые порты в старом локальном Compose ограничены loopback. В production наружу публикуется только Caddy.

## Проверки

- ZIP: сверка наличия всех исходных файлов, CRC, SHA-256 в обновлённом MANIFEST.json.
- Интеграционная статическая проверка: 25 PASS, 0 BLOCKED.
- Production preflight: пройдена; shell syntax обоих новых скриптов: пройдена.
- Целевые тесты VPS / integration / preflight: 10 passed.
- История: в первой VPS-редакции общие исходниковые тесты давали 79 passed, 2 failed (29 subtests passed). Обе ошибки исправлены в настоящей редакции; см. дополнение ниже.
- VEXA MAP: 49 passed (9 subtests passed).
- Не выполнены: полноценные Backend интеграционные тесты, реальные миграции PostgreSQL, Docker build/up, Android APK, web build, TLS выдача, запуск на VPS. VPS/GitHub не изменялись напрямую. CI проверяет целевые контракты; это не полная аттестация проекта. Автооткат не реализован; локальные DB backups не заменяют внешний backup.

## Изменённые исходные файлы

- `.env.example`
- `README-DEPLOYMENT-FIXES.md`
- `README.md`
- `README_LOCAL_SETUP.md`
- `START_HERE.txt`
- `android/client/app/build.gradle.kts`
- `android/client/gradle.properties`
- `android/driver/app/build.gradle.kts`
- `android/driver/gradle.properties`
- `backend/app/config.py`
- `backend/migrations/env.py`
- `dispatcher/.env.example`
- `docs/06_VPS_AND_DEPLOYMENT_GUIDE.md`
- `docs/ANDROID_BUILD.md`
- `docs/INSTALLATION.md`
- `docs/PRODUCTION_DEPLOYMENT_0.3.5.md`
- `docs/VEXA_SERVER_CONFIG.md`
- `infrastructure/Caddyfile.production`
- `infrastructure/compose.production.yml`
- `infrastructure/docker-compose.yml`
- `infrastructure/nginx-vexa.conf.example`
- `tools/release_preflight.py`

## Добавленные файлы

- `android/client/gradle/wrapper/gradle-wrapper.jar`
- `android/driver/gradle/wrapper/gradle-wrapper.jar`
- `tools/setup_vps.sh`
- `tools/deploy_vps.sh`
- `.github/workflows/deploy.yml`
- `tests/test_vps_config.py`
- `VPS_START_HERE.md`
- `VPS_CHANGE_REPORT.md`

## Исправление двух контрактов дизайна (VPS fixed)

- Android: сохранены versionName=0.3.19 и versionCode=19 обоих приложений. Тест теперь проверяет корректный формат, минимальную версию внедрения дизайна и совпадение версии и кода Client/Driver, без привязки к устаревшей 0.3.14. Существующая отдельная проверка версии 0.3.19 сохранена.
- VEXA MAP: фон #151D21 (graphite950) сохранён в коде карты. Метаданные и генератор палитры приведены в соответствие. #202A2F (graphite900) остаётся цветом карточек. Проверяются все определения фона в сервере (AST), а также реальные локальные HTTP-ответы растрового и векторного стилей (2D/3D).
- GitHub Actions: в предварительную проверку перед деплоем включены тесты дизайна.
- Повторный запуск `python -m pytest -q tests VEXA_MAP/tests`: 130 passed, 38 subtests passed; 0 failed. Backend-интеграция, сборка APK и реальный VPS не проверялись.
- Изменены только `tests/test_design_system_0_3_14.py`, `VEXA_MAP/design-palette.json`, `tools/sync_design_tokens.py`, `VEXA_MAP/tests/test_map_server.py`, `.github/workflows/deploy.yml`, этот отчёт и `MANIFEST.json`. Все остальные файлы сохранены побайтно.
