
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


PaymentMethod = Literal[
    "cash",
    "driver_transfer",
    "card",
    "sbp",
]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------
# ORDERS
# ------------------------------------------------------------

class OrderCreate(APIModel):
    # Публичный код города, не UUID из таблицы cities.
    city_code: str = Field(default="obolensk", min_length=1, max_length=80)
    tariff_id: UUID | None = None
    customer_name: str | None = Field(default=None, max_length=120)
    customer_phone: str = Field(min_length=5, max_length=40)

    anonymous: bool = False

    pickup_address: str = Field(min_length=2, max_length=500)
    destination_address: str = Field(min_length=2, max_length=500)

    pickup_latitude: float | None = Field(default=None, ge=-90, le=90)
    pickup_longitude: float | None = Field(default=None, ge=-180, le=180)

    destination_latitude: float | None = Field(default=None, ge=-90, le=90)
    destination_longitude: float | None = Field(default=None, ge=-180, le=180)

    payment_method: PaymentMethod = "cash"

    # Временно оставлено для переходной совместимости.
    # Backend не должен доверять цене, присланной клиентом.
    price_rub: int | None = Field(default=None, ge=0)

    comment: str | None = Field(default=None, max_length=2000)


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

    comment: str | None = None

    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------
# DISPATCHER AUTHENTICATION
# ------------------------------------------------------------

class DispatcherLogin(APIModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=128)


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
    city_code: str = Field(min_length=1, max_length=80)
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    vehicle_class: str = Field(min_length=1, max_length=80)

    base_price_kopecks: int = Field(ge=0)
    price_per_km_kopecks: int = Field(ge=0)
    price_per_minute_kopecks: int = Field(ge=0)

    minimum_fare_kopecks: int | None = Field(default=None, ge=0)
    maximum_fare_kopecks: int | None = Field(default=None, ge=0)

    is_active: bool = True


class TariffUpdate(APIModel):
    code: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    vehicle_class: str | None = Field(default=None, min_length=1, max_length=80)

    base_price_kopecks: int | None = Field(default=None, ge=0)
    price_per_km_kopecks: int | None = Field(default=None, ge=0)
    price_per_minute_kopecks: int | None = Field(default=None, ge=0)

    minimum_fare_kopecks: int | None = Field(default=None, ge=0)
    maximum_fare_kopecks: int | None = Field(default=None, ge=0)

    is_active: bool | None = None
