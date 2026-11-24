VEXA 0.3.41 VPS — актуальный запуск: VPS_START_HERE.md (в корне).
Публичный адрес: https://45.143.139.162. Нижеследующие инструкции относятся к прежним версиям или локальному режиму.

# VEXA 0.3.5 — перенос на реальный сервер (инструкция, НЕ факт развёртывания)

## До начала
1. Linux-сервер с Docker Engine + Docker Compose plugin, белый IP, DNS-имя (`VEXA_DOMAIN`).
2. Открыть только TCP 80/443 и при необходимости UDP 443. База, Redis, Backend, VEXA MAP и веб-панели **не публикуют** свои порты наружу.
3. Выделить объём RAM/диска под геоданные и отдельно подготовить MBTiles и OSRM-граф. В релизе их нет.
4. Настроить резервные копии Postgres и содержимого `VEXA_MAP/data`. Хранить копии отдельно от сервера, проверить восстановление.
5. Проверить лицензионные условия источников данных OSM/спутниковых снимков и требования РФ к персональным данным.

## Конфигурация
```bash
cp .env.production.example .env.production
# Вручную заменить VEXA_DOMAIN, VEXA_TLS_EMAIL, POSTGRES_PASSWORD,
# DATABASE_URL (тот же пароль), SECRET_KEY. НЕ публиковать файл.
python3 tools/release_preflight.py --env .env.production
```
Для пароля БД используйте длинную URL-safe строку; для `SECRET_KEY` — **другой** случайный секрет. DNS домена должен указывать на новый сервер, иначе Caddy не выпустит сертификат.

## Запуск (не смешивать с локальным docker-compose.yml)
```bash
docker compose --env-file .env.production -f infrastructure/compose.production.yml config --quiet
docker compose --env-file .env.production -f infrastructure/compose.production.yml up -d --build
# Миграции Alembic выполняются сервисом migrate до запуска API.
docker compose --env-file .env.production -f infrastructure/compose.production.yml ps
curl -fsS https://YOUR_DOMAIN/health
curl -fsS https://YOUR_DOMAIN/maps/health
```
Панель диспетчера: `https://YOUR_DOMAIN/dispatch/`; главный администратор: `https://YOUR_DOMAIN/admin/`. API: `https://YOUR_DOMAIN/api/`; карты: `https://YOUR_DOMAIN/maps/`.

## Android релизы
Клиент и водитель собираются **на машине с Android SDK**, не на сервере:
```bash
./gradlew :app:assembleRelease \
  -PvexaReleaseApiBaseUrl=https://YOUR_DOMAIN \
  -PvexaReleaseMapBaseUrl=https://YOUR_DOMAIN/maps
```
Указанные URL должны быть настоящими HTTPS-адресами. Release APK требуется подписать собственным keystore (не хранить ключи в проекте). Для локального тестирования используйте debug-сборки с HTTP на IP ПК.

## Карты/маршруты
MBTiles: `VEXA_MAP/data/regions/*.mbtiles`; адресный индекс: `VEXA_MAP/data/places.sqlite`; OSRM: `VEXA_MAP/data/osrm/region.osrm*`. Если OSRM-пакет готов, установить обе переменные `OSRM_BASE_URL` и `VEXA_MAP_OSRM_URL` равными `http://osrm:5000` и запускать с `--profile routing`. **Векторные PBF MBTiles пока не отображаются без полноценного векторного стиля; растровые MBTiles поддерживаются.**

## Проверка перед публичным запуском
- Админ и диспетчер входят отдельно, запрещён межролевой доступ.
- Клиент создаёт заказ, водитель получает предложение, поездка завершается, комиссия записана один раз даже при повторном запросе.
- 401/403, потеря сети, перезапуск контейнера, остановка Redis/OSRM обрабатываются без потери данных.
- Бэкапы проверены через восстановление в отдельную тестовую БД; включён журнал безопасности.
- Инструментально проверены APK и обе production веб-сборки, зависимости, миграции, SMS, реальные карты, нагрузочные сценарии.

## Резервные копии
`bash tools/backup_postgres.sh` создаёт локальный dump в `backups/`; настройте вынос во внешнее хранилище и периодическую проверку восстановления. Для восстановления **не используйте** рабочую БД напрямую без отдельного плана и подтверждения.

## Ограничения
Это заготовка для переноса, **не завершённый production rollout**. Не проверены сервер, Android APK, Play Store signing, TLS с реальным доменом, данные карт, целостность всех бизнес-процессов и юридические требования.
