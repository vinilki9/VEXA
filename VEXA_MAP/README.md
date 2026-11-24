> **0.3.20: Процесс подготовки реальных региональных OSM.PBF → векторные MBTiles + отдельный серверный граф OSRM (не включены в архив).** См. [REGIONAL_DATA_PIPELINE_0.3.20.md](REGIONAL_DATA_PIPELINE_0.3.20.md). Использование диска — до 250 ГиБ, обработка по одному округу.

> **0.3.19: Векторные PBF, камера Client только сверху, Driver 2D/3D.** См. [VECTOR_2D_3D_0.3.19.md](VECTOR_2D_3D_0.3.19.md). Реальные карты и APK не входят в релиз.

# VEXA MAP — локальный картографический сервис (история базовой версии 0.3.15)

Базовая версия обслуживала **растровые MBTiles** и локальную геобазу адресов. В 0.3.19 добавлена поддержка векторных PBF. Настоящие картографические пакеты России и полноценный офлайн-движок телефона по-прежнему не включены.

## Региональные карты

Кладите лицензированные растровые пакеты MBTiles в `VEXA_MAP/data/regions/` по федеральным округам, например:

```
VEXA_MAP/data/regions/
  central.mbtiles
  volga.mbtiles
  ural.mbtiles
```

Растровые файлы должны иметь совместимые форматы PNG, JPG или WEBP. Векторные PBF необходимо собирать с согласованной схемой слоёв, шрифтов и атрибуции. При совпадении тайла выбор зависит от порядка пакетов; для production используйте единый регламент подготовки всех округов. Поддерживаются прежние одиночные MBTiles, если передать путь к файлу. Векторные PBF-пакеты поддерживаются после этапа 0.3.19; для них требуется согласованная схема слоёв и локальные глифы. После замены/добавления файлов перезапустите сервис. Скачивание файлов OSM.PBF не создаёт MBTiles автоматически — это разные форматы.

Docker: `docker compose -f infrastructure/docker-compose.yml up -d --build vexa_map`.

Локально из корня проекта:

```
python VEXA_MAP/server/vexa_map_server.py --host 0.0.0.0 --port 8090 --mbtiles VEXA_MAP/data/regions --places VEXA_MAP/data/places.sqlite
```

API: `/health`, `/style.json`, `/tilejson.json`, `/tiles/{z}/{x}/{y}.png`, `/v1/search?q=...`, `/v1/route?start_lat=...&start_lon=...&end_lat=...&end_lon=...`. В `health` проверяйте `map_ready`, `package_count`, `vector_style_required` и `routing_configured` (последнее — настройка URL, а НЕ гарантия работоспособности графа).

## Адресный поиск

CSV из достоверного разрешённого источника с колонками `name,latitude,longitude`:

```
python VEXA_MAP/server/vexa_map_server.py --places VEXA_MAP/data/places.sqlite --import-places VEXA_MAP/data/places.csv
```

Это простой локальный индекс названий, не полный геокодер со всеми домами.

## Автомобильная маршрутизация OSRM

На Windows есть `tools/fetch_osm_region.ps1 -District central-fed-district` (только явная загрузка OSM.PBF). Для новых, неразрушающих сборок векторного MBTiles и серверного OSRM см. **`REGIONAL_DATA_PIPELINE_0.3.20.md`**. Старый `tools/prepare_osrm_region.ps1` оставлен для совместимости, но для новых сборок не рекомендуется. После подготовки включите профиль `routing` в Docker Compose и задайте **оба** адреса `http://osrm:5000` в `.env` для `VEXA_MAP_OSRM_URL` и `OSRM_BASE_URL`. Процесс OSRM требует памяти и дополнительного дискового пространства, и текущий профиль запускает только **один** выбранный регион. Межрегиональная маршрутизация и объединение графов ещё не реализованы.

Не скачивайте массово готовые тайлы с публичных серверов OpenStreetMap: используйте выгрузки геоданных и законный собственный рендеринг. При использовании OSM обязательны условия лицензии ODbL и указание авторства. Геоданные можно получить на https://download.geofabrik.de/russia.html; техническая документация OSRM: https://github.com/Project-OSRM/osrm-backend.

Запуск тестов без внешнего интернета: `python -m unittest discover -s VEXA_MAP/tests -v`.


## 0.3.15 — каталог и доставка офлайн-пакетов

Восемь федеральных округов в каталоге: `central`, `northwestern`, `southern`,
`north-caucasus`, `volga`, `ural`, `siberian`, `far-eastern`.
Каталог **не означает, что пакеты загружены**; по умолчанию все округа имеют
`available: false` до добавления настоящих растровых MBTiles и публикации.

После подготовки собственного лицензированного файла `data/regions/central.mbtiles`:

```shell
python VEXA_MAP/server/vexa_map_server.py --mbtiles VEXA_MAP/data/regions --publish-region central --data-version 2026.11
python VEXA_MAP/server/vexa_map_server.py --mbtiles VEXA_MAP/data/regions --verify-region central
```

Публикация создаёт `central.manifest.json` с `sha256`, размером в байтах,
версией данных, форматом, масштабами, атрибуцией. Для проверки крупного файла
контрольная сумма читается потоково; это не расходует гигабайты оперативной памяти.

Методы сервера:

- `GET /v1/offline/catalog` — каталог восьми округов с `available`.
- `GET /v1/offline/regions/central/manifest` — метаданные опубликованного пакета.
- `GET /v1/offline/regions/central/download` — потоковая выдача MBTiles с
  `Range`, `206`, `ETag`, `HEAD` и возобновлением по `If-Range`.

**Выдача скачиваемых пакетов по умолчанию отключена.** В изолированной локальной
сети можно явно включить параметром `--serve-offline-packs` или переменной
`VEXA_MAP_SERVE_OFFLINE_PACKS=1` в Docker Compose. При переносе на публичный
сервер нельзя открывать неавторизованный URL скачивания: нужен HTTPS,
авторизация/подписанные ссылки, квоты и правила лицензирования данных.
SHA-256 позволяет обнаружить битый файл при установке, но не заменяет цифровую
подпись издателя. Приложение должно проверять скачанные байты до активации.

**Ограничения:** загрузчик MBTiles внутри Android и отображение скачанных MBTiles
в MapLibre пока не подключены, маршруты OSRM офлайн на телефоне не работают.
Это инфраструктура распространения региональных данных, а не готовая
офлайн-навигация. Пакеты России, спутник и 3D в архив не включены.
