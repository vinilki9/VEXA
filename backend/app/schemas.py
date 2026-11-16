
from datetime import datetime
from typing import Literal
from uuid import UUID
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


PaymentMethod = Literal[
    "cash",
    "driver_transfer",
    "card",
    "sbp",
]


CARGO_VEHICLES = {
    "Универсал",
    "Каблук / небольшой фургон",
    "Средний грузовой фургон",
    "Газель",
}


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------
# ORDERS
# ------------------------------------------------------------

class OrderCreate(APIModel):
    # Публичный код города, не UUID из таблицы cities.
    city_code: str = Field(
        default="obolensk",
        min_length=1,
        max_length=80,
    )

    tariff_id: UUID | None = None

    customer_name: str | None = Field(
        default=None,
        max_length=120,
    )

    customer_phone: str = Field(
        min_length=5,
        max_length=40,
    )

    anonymous: bool = False

    pickup_address: str = Field(
        min_length=2,
        max_length=500,
    )

    destination_address: str = Field(
        min_length=2,
        max_length=500,
    )

    pickup_latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
    )

    pickup_longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
    )

    destination_latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
    )

    destination_longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
    )

    payment_method: PaymentMethod = "cash"

    # Подписанное сервером ценовое предложение.
    # Сервер проверяет подпись и срок действия перед созданием заказа.
    price_quote_token: str = Field(
        min_length=32,
        max_length=4096,
    )

    # Дополнительные услуги обычных тарифов.
    child_seat: bool = False
    animal_transport: bool = False

    # Параметры грузового заказа.
    cargo_vehicle: str | None = Field(
        default=None,
        max_length=80,
    )

    cargo_description: str | None = Field(
        default=None,
        max_length=2000,
    )

    cargo_loaders: int = Field(
        default=0,
        ge=0,
        le=4,
    )

    # Временно оставлено для переходной совместимости.
    # Backend не должен доверять цене, присланной клиентом.
    price_rub: int | None = Field(
        default=None,
        ge=0,
    )

    comment: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator("cargo_vehicle")
    @classmethod
    def validate_cargo_vehicle(cls, value):
        if value is not None and value not in CARGO_VEHICLES:
            raise ValueError("Недопустимый тип грузового автомобиля")

        return value


class OrderResponse(APIModel):
    id: UUID
    public_number: str

    # UUID города в базе данных.
    city_id: UUID
    tariff_id: UUID | None = None
    branch_id: UUID | None = None
    city_code: str

    passenger_user_id: UUID | None = None
    driver_user_id: UUID | None = None
    vehicle_id: UUID | None = None

    customer_name: str | None = None
    customer_phone: str
    anonymous: bool

    pickup_address: str
    destination_address: str

    pickup_latitude: float | None = None
    pickup_longitude: float | None = None
    destination_latitude: float | None = None
    destination_longitude: float | None = None

    route_distance_meters: int | None = None
    route_duration_seconds: int | None = None
    routing_provider: str | None = None

    status: str
    payment_method: PaymentMethod

    price_rub: int | None = None
    price_kopecks: int | None = None

    # Зафиксированный снимок динамического ценообразования.
    dynamic_pricing_settings_id: UUID | None = None
    dynamic_pricing_multiplier: Decimal | None = None
    dynamic_driver_distance_km: Decimal | None = None
    fare_dynamic_adjustment_kopecks: int | None = None
    dynamic_pricing_breakdown: dict | None = None

    # Основная расшифровка стоимости.
    fare_base_price_kopecks: int | None = None
    fare_distance_price_kopecks: int | None = None
    fare_time_price_kopecks: int | None = None
    fare_limit_adjustment_kopecks: int | None = None
    anonymous_surcharge_kopecks: int | None = None

    # Выбранные дополнительные услуги.
    child_seat: bool = False
    animal_transport: bool = False

    # Параметры грузового заказа.
    cargo_vehicle: str | None = None
    cargo_description: str | None = None
    cargo_loaders: int = 0

    # Сохранённая стоимость дополнительных услуг.
    child_seat_surcharge_kopecks: int | None = None
    animal_transport_surcharge_kopecks: int | None = None
    cargo_vehicle_surcharge_kopecks: int | None = None
    cargo_loaders_surcharge_kopecks: int | None = None

    comment: str | None = None

    created_at: datetime
    updated_at: datetime


class OrderPricePreviewResponse(APIModel):
    city_code: str
    tariff_id: UUID

    route_distance_meters: int
    route_duration_seconds: int
    routing_provider: str

    # Основная стоимость маршрута.
    fare_base_price_kopecks: int
    fare_distance_price_kopecks: int
    fare_time_price_kopecks: int
    fare_limit_adjustment_kopecks: int
    anonymous_surcharge_kopecks: int

    # Динамическое ценообразование.
    dynamic_pricing_settings_id: UUID | None = None
    dynamic_pricing_multiplier: Decimal
    dynamic_driver_distance_km: Decimal | None = None
    fare_dynamic_adjustment_kopecks: int
    dynamic_pricing_breakdown: dict

    # Дополнительные услуги.
    child_seat_surcharge_kopecks: int = 0
    animal_transport_surcharge_kopecks: int = 0
    cargo_vehicle_surcharge_kopecks: int = 0
    cargo_loaders_surcharge_kopecks: int = 0

    # Подписанное ценовое предложение.
    price_quote_token: str = Field(
        min_length=32,
        max_length=4096,
    )
    price_quote_expires_at: datetime

    # Итоговая предварительная стоимость.
    price_kopecks: int
    price_rub: int


# ------------------------------------------------------------
# DISPATCHER AUTHENTICATION
# ------------------------------------------------------------

class DispatcherLogin(APIModel):
    username: str = Field(
        min_length=3,
        max_length=80,
    )

    password: str = Field(
        min_length=1,
        max_length=128,
    )


class TokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"


class DispatcherResponse(APIModel):
    # UUID пользователя из таблицы users.
    id: UUID
    username: str
    is_active: bool
    role: str
    branch_id: UUID | None = None
    created_at: datetime


# ------------------------------------------------------------
# COMMON RESPONSES
# ------------------------------------------------------------

class CityResponse(APIModel):
    id: UUID
    code: str
    name: str
    is_active: bool


class MessageResponse(APIModel):
    message: str


# ------------------------------------------------------------
# TARIFF MANAGEMENT
# ------------------------------------------------------------

class TariffCreate(APIModel):
    city_code: str = Field(
        min_length=1,
        max_length=80,
    )

    code: str = Field(
        min_length=1,
        max_length=80,
    )

    name: str = Field(
        min_length=1,
        max_length=120,
    )

    vehicle_class: str = Field(
        min_length=1,
        max_length=80,
    )

    base_price_kopecks: int = Field(ge=0)
    price_per_km_kopecks: int = Field(ge=0)
    price_per_minute_kopecks: int = Field(ge=0)

    minimum_fare_kopecks: int | None = Field(
        default=None,
        ge=0,
    )

    maximum_fare_kopecks: int | None = Field(
        default=None,
        ge=0,
    )

    # Стоимость дополнительных услуг.
    child_seat_surcharge_kopecks: int = Field(
        default=10_000,
        ge=0,
    )

    animal_transport_surcharge_kopecks: int = Field(
        default=10_000,
        ge=0,
    )

    # Стоимость каждого типа грузового автомобиля.
    # Значения задаются в копейках.
    cargo_vehicle_surcharges: dict[str, int] = Field(
        default_factory=dict,
    )

    # Стоимость одного грузчика.
    cargo_loader_price_per_person_kopecks: int = Field(
        default=0,
        ge=0,
    )

    is_active: bool = True

    @field_validator("cargo_vehicle_surcharges", mode="before")
    @classmethod
    def validate_cargo_vehicle_surcharges(cls, value):
        if value is None:
            return {}

        if not isinstance(value, dict):
            raise ValueError("Стоимость грузовых автомобилей должна быть объектом")

        for vehicle, price in value.items():
            if vehicle not in CARGO_VEHICLES:
                raise ValueError(
                    f"Неизвестный тип грузового автомобиля: {vehicle}"
                )

            if type(price) is not int or price < 0:
                raise ValueError(
                    "Стоимость грузового автомобиля должна быть "
                    "целым неотрицательным числом в копейках"
                )

        return value


class TariffUpdate(APIModel):
    code: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
    )

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )

    vehicle_class: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
    )

    base_price_kopecks: int | None = Field(
        default=None,
        ge=0,
    )

    price_per_km_kopecks: int | None = Field(
        default=None,
        ge=0,
    )

    price_per_minute_kopecks: int | None = Field(
        default=None,
        ge=0,
    )

    minimum_fare_kopecks: int | None = Field(
        default=None,
        ge=0,
    )

    maximum_fare_kopecks: int | None = Field(
        default=None,
        ge=0,
    )

    child_seat_surcharge_kopecks: int | None = Field(
        default=None,
        ge=0,
    )

    animal_transport_surcharge_kopecks: int | None = Field(
        default=None,
        ge=0,
    )

    cargo_vehicle_surcharges: dict[str, int] | None = None

    cargo_loader_price_per_person_kopecks: int | None = Field(
        default=None,
        ge=0,
    )

    is_active: bool | None = None

    @field_validator("cargo_vehicle_surcharges", mode="before")
    @classmethod
    def validate_cargo_vehicle_surcharges(cls, value):
        if value is None:
            return None

        if not isinstance(value, dict):
            raise ValueError("Стоимость грузовых автомобилей должна быть объектом")

        for vehicle, price in value.items():
            if vehicle not in CARGO_VEHICLES:
                raise ValueError(
                    f"Неизвестный тип грузового автомобиля: {vehicle}"
                )

            if type(price) is not int or price < 0:
                raise ValueError(
                    "Стоимость грузового автомобиля должна быть "
                    "целым неотрицательным числом в копейках"
                )

        return value
