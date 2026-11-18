
-- ============================================================
-- VEXA DATABASE SCHEMA
-- PostgreSQL 16+
--
-- Reference schema: итоговая структура после Alembic 0013.
-- Первый пилот: Оболенск.
-- Архитектура: несколько городов и филиалов.
--
-- ВАЖНО:
-- 1. Канонический механизм изменения существующей БД —
--    Alembic migrations.
-- 2. Этот файл описывает итоговую структуру БД.
-- 3. Не запускать его поверх существующей базы данных.
-- 4. UUID и временные метки в основных таблицах формируются
--    приложением, если серверный DEFAULT не указан.
-- ============================================================

BEGIN;

-- ============================================================
-- 1. CITIES
-- ============================================================

CREATE TABLE cities (
    id UUID PRIMARY KEY NOT NULL,
    code VARCHAR(80) NOT NULL,
    name VARCHAR(120) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT cities_code_key UNIQUE (code)
);

CREATE INDEX ix_cities_code
    ON cities (code);


-- ============================================================
-- 2. USERS
-- Единая учётная запись для пассажиров, водителей,
-- диспетчеров и других ролей.
-- ============================================================

CREATE TABLE users (
    id UUID PRIMARY KEY NOT NULL,
    username VARCHAR(80),
    phone VARCHAR(40),
    password_hash VARCHAR(255),
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT users_username_key UNIQUE (username),
    CONSTRAINT users_phone_key UNIQUE (phone)
);


-- ============================================================
-- 3. BRANCHES
-- ============================================================

CREATE TABLE branches (
    id UUID PRIMARY KEY NOT NULL,
    city_id UUID NOT NULL REFERENCES cities(id),
    name VARCHAR(120) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_branches_city_name UNIQUE (city_id, name)
);

CREATE INDEX ix_branches_city_id
    ON branches (city_id);


-- ============================================================
-- 4. TARIFFS
-- Все денежные суммы хранятся в копейках.
-- ============================================================

CREATE TABLE tariffs (
    id UUID PRIMARY KEY NOT NULL,
    city_id UUID NOT NULL REFERENCES cities(id),
    code VARCHAR(80) NOT NULL,
    name VARCHAR(120) NOT NULL,
    vehicle_class VARCHAR(80) NOT NULL,

    base_price_kopecks INTEGER NOT NULL,
    price_per_km_kopecks INTEGER NOT NULL,
    price_per_minute_kopecks INTEGER NOT NULL,

    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,

    minimum_fare_kopecks INTEGER,
    maximum_fare_kopecks INTEGER,

    child_seat_surcharge_kopecks INTEGER
        NOT NULL DEFAULT 10000,

    animal_transport_surcharge_kopecks INTEGER
        NOT NULL DEFAULT 10000,

    cargo_vehicle_surcharges JSON
        NOT NULL DEFAULT '{}'::json,

    cargo_loader_price_per_person_kopecks INTEGER
        NOT NULL DEFAULT 0,

    CONSTRAINT uq_tariffs_city_code
        UNIQUE (city_id, code),

    CONSTRAINT tariffs_base_price_nonnegative
        CHECK (base_price_kopecks >= 0),

    CONSTRAINT tariffs_price_per_km_nonnegative
        CHECK (price_per_km_kopecks >= 0),

    CONSTRAINT tariffs_price_per_minute_nonnegative
        CHECK (price_per_minute_kopecks >= 0),

    CONSTRAINT tariffs_minimum_fare_nonnegative
        CHECK (
            minimum_fare_kopecks IS NULL
            OR minimum_fare_kopecks >= 0
        ),

    CONSTRAINT tariffs_maximum_fare_nonnegative
        CHECK (
            maximum_fare_kopecks IS NULL
            OR maximum_fare_kopecks >= 0
        ),

    CONSTRAINT tariffs_maximum_fare_gte_minimum
        CHECK (
            minimum_fare_kopecks IS NULL
            OR maximum_fare_kopecks IS NULL
            OR maximum_fare_kopecks >= minimum_fare_kopecks
        ),

    CONSTRAINT tariffs_child_seat_surcharge_nonnegative
        CHECK (child_seat_surcharge_kopecks >= 0),

    CONSTRAINT tariffs_animal_surcharge_nonnegative
        CHECK (animal_transport_surcharge_kopecks >= 0),

    CONSTRAINT tariffs_cargo_loader_price_nonnegative
        CHECK (cargo_loader_price_per_person_kopecks >= 0)
);

CREATE INDEX ix_tariffs_city_id
    ON tariffs (city_id);


-- ============================================================
-- 5. PASSENGER PROFILES
-- ============================================================

CREATE TABLE passenger_profiles (
    user_id UUID PRIMARY KEY NOT NULL REFERENCES users(id),
    display_name VARCHAR(120),
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);


-- ============================================================
-- 6. DRIVER PROFILES
-- ============================================================

CREATE TABLE driver_profiles (
    user_id UUID PRIMARY KEY NOT NULL REFERENCES users(id),
    city_id UUID NOT NULL REFERENCES cities(id),
    branch_id UUID REFERENCES branches(id),
    is_active BOOLEAN NOT NULL,
    is_online BOOLEAN NOT NULL,
    rating NUMERIC(3, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_driver_profiles_city_id
    ON driver_profiles (city_id);

CREATE INDEX ix_driver_profiles_branch_id
    ON driver_profiles (branch_id);


-- ============================================================
-- 7. DISPATCHER PROFILES
-- ============================================================

CREATE TABLE dispatcher_profiles (
    user_id UUID PRIMARY KEY NOT NULL REFERENCES users(id),
    branch_id UUID REFERENCES branches(id),
    role VARCHAR(40) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_dispatcher_profiles_branch_id
    ON dispatcher_profiles (branch_id);


-- ============================================================
-- 8. VEHICLES
-- ============================================================

CREATE TABLE vehicles (
    id UUID PRIMARY KEY NOT NULL,
    driver_user_id UUID NOT NULL
        REFERENCES driver_profiles(user_id),
    city_id UUID NOT NULL REFERENCES cities(id),
    make VARCHAR(80) NOT NULL,
    model VARCHAR(80) NOT NULL,
    color VARCHAR(50) NOT NULL,
    license_plate VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT vehicles_license_plate_key UNIQUE (license_plate)
);

CREATE INDEX ix_vehicles_driver_user_id
    ON vehicles (driver_user_id);

CREATE INDEX ix_vehicles_city_id
    ON vehicles (city_id);


-- ============================================================
-- 9. CITY ORDER COUNTERS
-- ============================================================

CREATE TABLE city_order_counters (
    city_id UUID PRIMARY KEY NOT NULL REFERENCES cities(id),
    last_number INTEGER NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);


-- ============================================================
-- 10. ORDERS
-- ============================================================

CREATE TABLE orders (
    id UUID PRIMARY KEY NOT NULL,
    public_number VARCHAR(40) NOT NULL,

    city_id UUID NOT NULL REFERENCES cities(id),
    tariff_id UUID REFERENCES tariffs(id),
    branch_id UUID REFERENCES branches(id),

    passenger_user_id UUID
        REFERENCES passenger_profiles(user_id),

    driver_user_id UUID
        REFERENCES driver_profiles(user_id),

    vehicle_id UUID REFERENCES vehicles(id),

    customer_name VARCHAR(120),
    customer_phone VARCHAR(40) NOT NULL,
    anonymous BOOLEAN NOT NULL,

    pickup_address VARCHAR(500) NOT NULL,
    destination_address VARCHAR(500) NOT NULL,

    pickup_latitude FLOAT,
    pickup_longitude FLOAT,
    destination_latitude FLOAT,
    destination_longitude FLOAT,

    status VARCHAR(40) NOT NULL,
    payment_method VARCHAR(30) NOT NULL,

    price_rub INTEGER,
    price_kopecks INTEGER,

    comment TEXT,
    idempotency_key VARCHAR(128) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    route_distance_meters INTEGER,
    route_duration_seconds INTEGER,
    routing_provider VARCHAR(40),

    fare_base_price_kopecks INTEGER,
    fare_distance_price_kopecks INTEGER,
    fare_time_price_kopecks INTEGER,
    fare_limit_adjustment_kopecks INTEGER,
    anonymous_surcharge_kopecks INTEGER,

    child_seat BOOLEAN NOT NULL DEFAULT FALSE,
    animal_transport BOOLEAN NOT NULL DEFAULT FALSE,
    cargo_vehicle VARCHAR(80),
    cargo_description TEXT,
    cargo_loaders INTEGER NOT NULL DEFAULT 0,

    child_seat_surcharge_kopecks INTEGER,
    animal_transport_surcharge_kopecks INTEGER,
    cargo_vehicle_surcharge_kopecks INTEGER,
    cargo_loaders_surcharge_kopecks INTEGER,

    dynamic_pricing_settings_id UUID,
    dynamic_pricing_multiplier NUMERIC(5, 2),
    dynamic_driver_distance_km NUMERIC(8, 2),
    fare_dynamic_adjustment_kopecks INTEGER,
    dynamic_pricing_breakdown JSON,

    CONSTRAINT uq_orders_city_idempotency
        UNIQUE (city_id, idempotency_key),

    CONSTRAINT uq_orders_public_number
        UNIQUE (public_number),

    CONSTRAINT orders_price_rub_nonnegative
        CHECK (price_rub IS NULL OR price_rub >= 0),

    CONSTRAINT orders_price_kopecks_nonnegative
        CHECK (price_kopecks IS NULL OR price_kopecks >= 0),

    CONSTRAINT orders_cargo_loaders_range
        CHECK (cargo_loaders >= 0 AND cargo_loaders <= 4),

    CONSTRAINT orders_fare_breakdown_consistent
        CHECK (
            (
                fare_base_price_kopecks IS NULL
                AND fare_distance_price_kopecks IS NULL
                AND fare_time_price_kopecks IS NULL
                AND fare_limit_adjustment_kopecks IS NULL
                AND anonymous_surcharge_kopecks IS NULL
                AND child_seat_surcharge_kopecks IS NULL
                AND animal_transport_surcharge_kopecks IS NULL
                AND cargo_vehicle_surcharge_kopecks IS NULL
                AND cargo_loaders_surcharge_kopecks IS NULL
                AND fare_dynamic_adjustment_kopecks IS NULL
            )
            OR
            (
                fare_base_price_kopecks IS NOT NULL
                AND fare_dynamic_adjustment_kopecks IS NOT NULL
                AND fare_distance_price_kopecks IS NOT NULL
                AND fare_time_price_kopecks IS NOT NULL
                AND fare_limit_adjustment_kopecks IS NOT NULL
                AND anonymous_surcharge_kopecks IS NOT NULL
                AND child_seat_surcharge_kopecks IS NOT NULL
                AND animal_transport_surcharge_kopecks IS NOT NULL
                AND cargo_vehicle_surcharge_kopecks IS NOT NULL
                AND cargo_loaders_surcharge_kopecks IS NOT NULL
                AND price_kopecks IS NOT NULL

                AND fare_dynamic_adjustment_kopecks >= 0
                AND fare_base_price_kopecks >= 0
                AND fare_distance_price_kopecks >= 0
                AND fare_time_price_kopecks >= 0
                AND anonymous_surcharge_kopecks >= 0
                AND child_seat_surcharge_kopecks >= 0
                AND animal_transport_surcharge_kopecks >= 0
                AND cargo_vehicle_surcharge_kopecks >= 0
                AND cargo_loaders_surcharge_kopecks >= 0

                AND price_kopecks =
                    fare_base_price_kopecks
                    + fare_dynamic_adjustment_kopecks
                    + fare_distance_price_kopecks
                    + fare_time_price_kopecks
                    + fare_limit_adjustment_kopecks
                    + anonymous_surcharge_kopecks
                    + child_seat_surcharge_kopecks
                    + animal_transport_surcharge_kopecks
                    + cargo_vehicle_surcharge_kopecks
                    + cargo_loaders_surcharge_kopecks
            )
        )
);

CREATE INDEX ix_orders_city_id
    ON orders (city_id);

CREATE INDEX ix_orders_tariff_id
    ON orders (tariff_id);

CREATE INDEX ix_orders_branch_id
    ON orders (branch_id);

CREATE INDEX ix_orders_driver_user_id
    ON orders (driver_user_id);

CREATE INDEX ix_orders_status
    ON orders (status);

CREATE INDEX ix_orders_city_status_created
    ON orders (city_id, status, created_at);

CREATE INDEX ix_orders_dynamic_pricing_settings_id
    ON orders (dynamic_pricing_settings_id);


-- ============================================================
-- 11. ORDER STATUS HISTORY
-- ============================================================

CREATE TABLE order_status_history (
    id UUID PRIMARY KEY NOT NULL,
    order_id UUID NOT NULL REFERENCES orders(id),
    old_status VARCHAR(40),
    new_status VARCHAR(40) NOT NULL,
    changed_by_user_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_order_status_history_order_id
    ON order_status_history (order_id);


-- ============================================================
-- 12. TARIFF CHANGE HISTORY
-- ============================================================

CREATE TABLE tariff_change_history (
    id UUID PRIMARY KEY NOT NULL,

    tariff_id UUID NOT NULL
        REFERENCES tariffs(id) ON DELETE RESTRICT,

    city_id UUID NOT NULL
        REFERENCES cities(id) ON DELETE RESTRICT,

    changed_by_user_id UUID NOT NULL
        REFERENCES users(id) ON DELETE RESTRICT,

    action VARCHAR(20) NOT NULL,
    old_values JSON,
    new_values JSON NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_tariff_history_city_changed
    ON tariff_change_history (city_id, changed_at);

CREATE INDEX ix_tariff_history_tariff_changed
    ON tariff_change_history (tariff_id, changed_at);

CREATE INDEX ix_tariff_change_history_changed_by_user_id
    ON tariff_change_history (changed_by_user_id);

CREATE INDEX ix_tariff_change_history_changed_at
    ON tariff_change_history (changed_at);


-- ============================================================
-- 13. PASSENGER AUTH SESSIONS
-- ============================================================

CREATE TABLE passenger_auth_sessions (
    id UUID PRIMARY KEY NOT NULL,

    phone VARCHAR(20) NOT NULL,
    provider VARCHAR(30) NOT NULL,
    provider_session_id VARCHAR(120) NOT NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    provider_status VARCHAR(80),

    attempts INTEGER NOT NULL DEFAULT 0,

    expires_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_passenger_auth_sessions_phone
    ON passenger_auth_sessions (phone);

CREATE INDEX ix_passenger_auth_phone_created
    ON passenger_auth_sessions (phone, created_at);

CREATE INDEX ix_passenger_auth_expires
    ON passenger_auth_sessions (expires_at);


-- ============================================================
-- 14. DRIVER LOCATIONS
-- ============================================================

CREATE TABLE driver_locations (
    driver_user_id UUID PRIMARY KEY NOT NULL
        REFERENCES driver_profiles(user_id) ON DELETE CASCADE,

    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    accuracy_meters FLOAT,

    recorded_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT driver_locations_latitude_range
        CHECK (latitude >= -90 AND latitude <= 90),

    CONSTRAINT driver_locations_longitude_range
        CHECK (longitude >= -180 AND longitude <= 180),

    CONSTRAINT driver_locations_accuracy_nonnegative
        CHECK (
            accuracy_meters IS NULL
            OR accuracy_meters >= 0
        )
);

CREATE INDEX ix_driver_locations_recorded_at
    ON driver_locations (recorded_at);


-- ============================================================
-- 15. DRIVER FINANCE TRANSACTIONS
-- ============================================================

CREATE TABLE driver_finance_transactions (
    id UUID PRIMARY KEY NOT NULL,

    driver_user_id UUID NOT NULL
        REFERENCES driver_profiles(user_id) ON DELETE RESTRICT,

    order_id UUID
        REFERENCES orders(id) ON DELETE RESTRICT,

    city_id UUID NOT NULL
        REFERENCES cities(id) ON DELETE RESTRICT,

    branch_id UUID
        REFERENCES branches(id) ON DELETE RESTRICT,

    transaction_type VARCHAR(40) NOT NULL,
    payment_method VARCHAR(30) NOT NULL,

    driver_rating NUMERIC(3, 2),

    fare_kopecks INTEGER NOT NULL,
    commission_rate_percent NUMERIC(5, 2) NOT NULL,
    commission_kopecks INTEGER NOT NULL,
    driver_earning_kopecks INTEGER NOT NULL,

    debt_change_kopecks INTEGER NOT NULL DEFAULT 0,

    description TEXT,
    created_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT uq_driver_finance_order_type
        UNIQUE (order_id, transaction_type),

    CONSTRAINT driver_finance_fare_nonnegative
        CHECK (fare_kopecks >= 0),

    CONSTRAINT driver_finance_commission_rate_range
        CHECK (
            commission_rate_percent >= 0
            AND commission_rate_percent <= 100
        ),

    CONSTRAINT driver_finance_commission_nonnegative
        CHECK (commission_kopecks >= 0),

    CONSTRAINT driver_finance_earning_nonnegative
        CHECK (driver_earning_kopecks >= 0)
);

CREATE INDEX ix_driver_finance_transactions_driver_user_id
    ON driver_finance_transactions (driver_user_id);

CREATE INDEX ix_driver_finance_transactions_order_id
    ON driver_finance_transactions (order_id);

CREATE INDEX ix_driver_finance_transactions_city_id
    ON driver_finance_transactions (city_id);

CREATE INDEX ix_driver_finance_transactions_branch_id
    ON driver_finance_transactions (branch_id);

CREATE INDEX ix_driver_finance_driver_created
    ON driver_finance_transactions (driver_user_id, created_at);

CREATE INDEX ix_driver_finance_city_created
    ON driver_finance_transactions (city_id, created_at);


-- ============================================================
-- 16. DRIVER BRANCH TRANSFERS
-- ============================================================

CREATE TABLE driver_branch_transfers (
    id UUID PRIMARY KEY NOT NULL,

    driver_user_id UUID NOT NULL
        REFERENCES driver_profiles(user_id) ON DELETE RESTRICT,

    from_city_id UUID
        REFERENCES cities(id) ON DELETE RESTRICT,

    to_city_id UUID NOT NULL
        REFERENCES cities(id) ON DELETE RESTRICT,

    from_branch_id UUID
        REFERENCES branches(id) ON DELETE RESTRICT,

    to_branch_id UUID NOT NULL
        REFERENCES branches(id) ON DELETE RESTRICT,

    debt_kopecks_at_transfer INTEGER NOT NULL,

    transferred_by_user_id UUID NOT NULL
        REFERENCES users(id) ON DELETE RESTRICT,

    created_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT driver_branch_transfers_debt_nonnegative
        CHECK (debt_kopecks_at_transfer >= 0),

    CONSTRAINT driver_branch_transfers_different_branches
        CHECK (
            from_branch_id IS NULL
            OR from_branch_id != to_branch_id
        )
);

CREATE INDEX ix_driver_branch_transfers_driver_user_id
    ON driver_branch_transfers (driver_user_id);

CREATE INDEX ix_driver_branch_transfers_from_city_id
    ON driver_branch_transfers (from_city_id);

CREATE INDEX ix_driver_branch_transfers_to_city_id
    ON driver_branch_transfers (to_city_id);

CREATE INDEX ix_driver_branch_transfers_from_branch_id
    ON driver_branch_transfers (from_branch_id);

CREATE INDEX ix_driver_branch_transfers_to_branch_id
    ON driver_branch_transfers (to_branch_id);

CREATE INDEX ix_driver_branch_transfers_transferred_by_user_id
    ON driver_branch_transfers (transferred_by_user_id);

CREATE INDEX ix_driver_branch_transfers_driver_user_id_created_at
    ON driver_branch_transfers (driver_user_id, created_at);

CREATE INDEX ix_driver_branch_transfers_from_city_id_created_at
    ON driver_branch_transfers (from_city_id, created_at);

CREATE INDEX ix_driver_branch_transfers_to_city_id_created_at
    ON driver_branch_transfers (to_city_id, created_at);


-- ============================================================
-- 17. DYNAMIC PRICING SETTINGS
-- ============================================================

CREATE TABLE dynamic_pricing_settings (
    id UUID PRIMARY KEY NOT NULL,

    city_id UUID NOT NULL
        REFERENCES cities(id) ON DELETE RESTRICT,

    branch_id UUID
        REFERENCES branches(id) ON DELETE RESTRICT,

    max_multiplier NUMERIC(5, 2) NOT NULL DEFAULT 2.50,

    driver_radius_km NUMERIC(6, 2) NOT NULL DEFAULT 4.00,

    driver_distance_start_multiplier
        NUMERIC(5, 2) NOT NULL DEFAULT 1.50,

    driver_distance_threshold_km
        NUMERIC(6, 2) NOT NULL DEFAULT 20.00,

    driver_distance_threshold_multiplier
        NUMERIC(5, 2) NOT NULL DEFAULT 2.00,

    driver_distance_step_km
        NUMERIC(6, 2) NOT NULL DEFAULT 3.00,

    driver_distance_step_multiplier
        NUMERIC(5, 2) NOT NULL DEFAULT 0.20,

    weather_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    weather_addition NUMERIC(5, 2) NOT NULL DEFAULT 0.00,

    traffic_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    traffic_addition NUMERIC(5, 2) NOT NULL DEFAULT 0.00,

    demand_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    demand_addition NUMERIC(5, 2) NOT NULL DEFAULT 0.00,

    other_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    other_addition NUMERIC(5, 2) NOT NULL DEFAULT 0.00,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT dynamic_pricing_max_multiplier_min
        CHECK (max_multiplier >= 1.0),

    CONSTRAINT dynamic_pricing_driver_radius_nonnegative
        CHECK (driver_radius_km >= 0),

    CONSTRAINT dynamic_pricing_driver_start_min
        CHECK (driver_distance_start_multiplier >= 1.0),

    CONSTRAINT dynamic_pricing_driver_threshold_gt_radius
        CHECK (driver_distance_threshold_km > driver_radius_km),

    CONSTRAINT dynamic_pricing_driver_threshold_multiplier_valid
        CHECK (
            driver_distance_threshold_multiplier
            >= driver_distance_start_multiplier
        ),

    CONSTRAINT dynamic_pricing_driver_step_km_positive
        CHECK (driver_distance_step_km > 0),

    CONSTRAINT dynamic_pricing_driver_step_multiplier_nonnegative
        CHECK (driver_distance_step_multiplier >= 0),

    CONSTRAINT uq_dynamic_pricing_city_branch
        UNIQUE (city_id, branch_id)
);

CREATE INDEX ix_dynamic_pricing_settings_city_id
    ON dynamic_pricing_settings (city_id);

CREATE INDEX ix_dynamic_pricing_settings_branch_id
    ON dynamic_pricing_settings (branch_id);

CREATE INDEX ix_dynamic_pricing_city_branch
    ON dynamic_pricing_settings (city_id, branch_id);

-- Внешний ключ добавляется после создания таблицы
-- dynamic_pricing_settings, на которую он ссылается.
ALTER TABLE orders
    ADD CONSTRAINT fk_orders_dynamic_pricing_settings_id_dynamic_pricing_settings
    FOREIGN KEY (dynamic_pricing_settings_id)
    REFERENCES dynamic_pricing_settings(id)
    ON DELETE RESTRICT;


-- ============================================================
-- 18. DYNAMIC PRICING CHANGE HISTORY
-- ============================================================

CREATE TABLE dynamic_pricing_change_history (
    id UUID PRIMARY KEY NOT NULL,

    settings_id UUID NOT NULL
        REFERENCES dynamic_pricing_settings(id) ON DELETE RESTRICT,

    city_id UUID NOT NULL
        REFERENCES cities(id) ON DELETE RESTRICT,

    branch_id UUID
        REFERENCES branches(id) ON DELETE RESTRICT,

    changed_by_user_id UUID NOT NULL
        REFERENCES users(id) ON DELETE RESTRICT,

    action VARCHAR(20) NOT NULL,
    old_values JSON,
    new_values JSON NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_dynamic_pricing_change_history_settings_id
    ON dynamic_pricing_change_history (settings_id);

CREATE INDEX ix_dynamic_pricing_change_history_changed_by_user_id
    ON dynamic_pricing_change_history (changed_by_user_id);

CREATE INDEX ix_dynamic_pricing_history_city_changed
    ON dynamic_pricing_change_history (city_id, changed_at);

CREATE INDEX ix_dynamic_pricing_history_settings_changed
    ON dynamic_pricing_change_history (settings_id, changed_at);

CREATE INDEX ix_dynamic_pricing_change_history_changed_at
    ON dynamic_pricing_change_history (changed_at);


-- ============================================================
-- 19. DRIVER ORDER OFFERS
-- История предложений заказов водителям.
-- ============================================================

CREATE TABLE driver_order_offers (
    id UUID PRIMARY KEY NOT NULL,

    order_id UUID NOT NULL
        REFERENCES orders(id) ON DELETE RESTRICT,

    driver_user_id UUID NOT NULL
        REFERENCES driver_profiles(user_id) ON DELETE RESTRICT,

    vehicle_id UUID NOT NULL
        REFERENCES vehicles(id) ON DELETE RESTRICT,

    status VARCHAR(20) NOT NULL,
    attempt_number INTEGER NOT NULL,

    response_timeout_seconds INTEGER NOT NULL,

    distance_meters INTEGER,

    offered_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    responded_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT uq_driver_order_offers_order_driver
        UNIQUE (order_id, driver_user_id),

    CONSTRAINT driver_order_offers_status_valid
        CHECK (
            status IN (
                'pending',
                'accepted',
                'rejected',
                'expired',
                'cancelled'
            )
        ),

    CONSTRAINT driver_order_offers_timeout_positive
        CHECK (response_timeout_seconds > 0),

    CONSTRAINT driver_order_offers_distance_nonnegative
        CHECK (
            distance_meters IS NULL
            OR distance_meters >= 0
        )
);

CREATE INDEX ix_driver_order_offers_order_status
    ON driver_order_offers (order_id, status);

CREATE INDEX ix_driver_order_offers_driver_status
    ON driver_order_offers (driver_user_id, status);

CREATE INDEX ix_driver_order_offers_status_expires
    ON driver_order_offers (status, expires_at);


-- ============================================================
-- END OF VEXA DATABASE SCHEMA
-- ============================================================

COMMIT;
