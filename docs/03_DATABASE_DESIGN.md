# 03. Проектирование базы данных

Это согласованный каркас сущностей и правил хранения. Он задаёт направление для SQLAlchemy-моделей и Alembic-миграций; окончательные типы, индексы и ограничения должны быть оформлены в миграциях и проверены тестами.

## 1. Общие правила
- PostgreSQL.
- Первичные ключи — UUID.
- Время — UTC, тип `TIMESTAMPTZ`.
- Деньги — целые значения в копейках (`BIGINT` или подходящий целочисленный тип); валюта хранится явно, если платформа будет мультивалютной.
- Для изменяемых сущностей использовать `created_at`, `updated_at`; для мягкого удаления — `deleted_at`, где это оправдано.
- Критичные изменения фиксировать в истории/аудите.
- Для бизнес-данных организации использовать `organization_id`; для филиальных данных — `branch_id`, когда применимо.
- Внешние ключи и уникальные ограничения должны учитывать границы организации, чтобы исключить случайные межорганизационные связи.

## 2. Организации и география
### `organizations`
- `id`
- `name`
- `slug`
- `status`
- `created_at`, `updated_at`

### `organization_settings`
- `id`
- `organization_id`
- `settings_json`
- `updated_at`

### `cities`
- `id`
- `name`
- `region`
- `country_code`
- `timezone`

### `organization_cities`
Связь организации с городами обслуживания:
- `id`
- `organization_id`
- `city_id`
- `is_active`

### `branches`
- `id`
- `organization_id`
- `city_id`
- `name`
- `address`
- `status`

### `branch_settings`
- `id`
- `branch_id`
- `settings_json`
- `updated_at`

## 3. Пользователи, роли и доступ
### `users`
- `id`
- `phone` (обязательный идентификатор входа)
- `phone_verified_at`
- `created_at`, `updated_at`

### `user_profiles`
- `user_id`
- `first_name`
- `last_name` (необязательно)
- `middle_name` (необязательно)
- `profile_completed_at`

ФИО пассажира необязательно. Водительский профиль может требовать дополнительных данных по отдельным правилам допуска.

### `auth_otps`
- `id`
- `phone`
- `code_hash`
- `expires_at`
- `attempts`
- `consumed_at`
- `created_at`

### `memberships`
Связь пользователя с организацией/филиалом:
- `id`
- `user_id`
- `organization_id`
- `branch_id` (nullable, если доступ на уровне всей организации)
- `status`

### `roles`, `permissions`, `role_permissions`, `membership_roles`
Ролевой доступ. Предусмотреть системные и организационные роли; не зашивать права только в мобильный клиент.

Ранее определённые категории доступа:
- платформа;
- владелец/администратор компании;
- финансовый сотрудник;
- руководитель филиала;
- диспетчер;
- водитель;
- пассажир.

## 4. Пассажиры, водители и автомобили
### `passengers`
- `id`
- `user_id`
- `default_payment_method` (nullable)
- `created_at`

### `drivers`
- `id`
- `user_id`
- `organization_id`
- `status`
- `rating_cached` (производное значение, если используется)
- `created_at`, `updated_at`

### `vehicles`
- `id`
- `organization_id`
- `driver_id` (nullable/текущий водитель по бизнес-правилу)
- `make`, `model`, `color`
- `registration_number`
- `capacity`
- `status`

### `driver_shifts` / `driver_presence`
Для состояния на линии и доступности водителя:
- `id`
- `organization_id`
- `branch_id`
- `driver_id`
- `state`
- `started_at`
- `ended_at`
- `last_location_at`

### `driver_locations`
- `id`
- `organization_id`
- `driver_id`
- `latitude`, `longitude`
- `recorded_at`

Хранение координат требует отдельной политики срока хранения и доступа.

## 5. Заказы и поездки
### `orders`
- `id`
- `organization_id`
- `branch_id`
- `city_id`
- `passenger_id`
- `status`
- `tariff_id`
- `payment_method`
- `is_anonymous`
- `anonymous_fee_minor` — 10000 копеек для доплаты 100 ₽
- `estimated_price_minor`
- `final_price_minor`
- `currency`
- `pickup_address_id`
- `destination_address_id`
- `assigned_driver_id` (nullable)
- `created_at`, `updated_at`

### `order_addresses`
- `id`
- `order_id`
- `kind` (`pickup` / `destination`)
- `address_text`
- `latitude`, `longitude`
- `entrance`, `comment`

### `order_events`
- `id`
- `organization_id`
- `order_id`
- `event_type`
- `from_status`
- `to_status`
- `actor_user_id`
- `payload_json`
- `created_at`

### `dispatch_offers`
Предложения заказа водителям:
- `id`
- `organization_id`
- `order_id`
- `driver_id`
- `status` (например, pending/accepted/rejected/expired/cancelled)
- `offered_at`
- `responded_at`
- `expires_at`

### `trips`
- `id`
- `organization_id`
- `branch_id`
- `order_id` (уникальная связь, если одна поездка на заказ)
- `driver_id`
- `started_at`
- `completed_at`
- `distance_meters` (nullable)
- `duration_seconds` (nullable)
- `final_price_minor`

### `trip_status_history`
- `id`
- `trip_id`
- `from_status`
- `to_status`
- `actor_user_id`
- `created_at`
- `metadata_json`

## 6. Тарифы и цены
### `tariffs`
- `id`
- `organization_id`
- `branch_id` (nullable для тарифа уровня организации)
- `city_id`
- `name`
- `is_active`

### `tariff_rules` / `pricing_rules`
- `id`
- `tariff_id`
- `base_price_minor`
- `included_distance_meters`
- `price_per_km_minor`
- `price_per_minute_minor`
- `minimum_price_minor`
- `effective_from`, `effective_to`

Состав тарифа и формула цены должны быть отдельно утверждены до реализации расчётного движка.

## 7. Платежи и бухгалтерский регистр
### `payments`
- `id`
- `organization_id`
- `order_id`
- `trip_id`
- `method` (`cash`, `driver_transfer`, `card`, `sbp`)
- `status`
- `amount_minor`
- `currency`
- `provider`
- `provider_payment_id`
- `paid_at`

### `ledger_accounts`
Счета/субсчета учёта пассажира, водителя, компании и платформы — конкретная модель счетов подлежит утверждению.

### `ledger_entries`
- `id`
- `organization_id`
- `trip_id`
- `account_id`
- `entry_type`
- `amount_minor`
- `currency`
- `created_at`
- `reversal_of_entry_id` (nullable)

### `driver_balances` (проекция/кэш, если понадобится)
Баланс должен быть производным от регистра, а не единственным источником финансовой истины.

### `payouts`
- `id`
- `organization_id`
- `driver_id`
- `amount_minor`
- `status`
- `requested_at`
- `processed_at`

Комиссия 10% рассчитывается от суммы, определённой утверждённым правилом тарификации/финального чека, для завершённой поездки. Точная база расчёта и бухгалтерские проводки должны быть закреплены в финансовой спецификации до запуска реальных расчётов.

## 8. Рейтинг и уведомления
### `ratings`
- `id`
- `organization_id`
- `trip_id`
- `passenger_id`
- `driver_id`
- `score`
- `comment` (nullable)
- `created_at`

Расчёт отображаемого рейтинга: последние 50 действительных оценок водителя. Нужны индексы по `(driver_id, created_at DESC)` и фильтры по организации.

### `notifications`
- `id`
- `organization_id`
- `user_id`
- `channel`
- `template_key`
- `payload_json`
- `status`
- `created_at`, `sent_at`

## 9. Аудит
### `audit_logs`
- `id`
- `organization_id` (nullable для платформенных событий)
- `actor_user_id`
- `action`
- `entity_type`
- `entity_id`
- `before_json`
- `after_json`
- `ip_address` (если допустимо политикой приватности)
- `created_at`

## 10. Критические ограничения и транзакции
- Назначение водителя — транзакционно и атомарно.
- Один заказ не может одновременно иметь двух активных назначенных водителей.
- Нельзя завершить поездку без корректного перехода статуса.
- Платёж и финансовые проводки должны быть идемпотентны по внешнему идентификатору/ключу операции.
- Нельзя смешивать записи разных `organization_id`.
- Корректировки финансов проводить сторнирующими записями, не переписывать историю задним числом.
