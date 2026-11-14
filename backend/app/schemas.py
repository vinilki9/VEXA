
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PaymentMethod = Literal[
    "cash",
    "driver_transfer",
    "card",
    "sbp",
]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Создание заказа клиентом
class OrderCreate(APIModel):
    city_id: str = Field(default="obolensk", max_length=80)

    customer_name: str | None = Field(default=None, max_length=120)
    customer_phone: str = Field(min_length=5, max_length=40)

    anonymous: bool = False

    pickup_address: str = Field(min_length=2, max_length=500)
    destination_address: str = Field(min_length=2, max_length=500)

    pickup_latitude: float | None = Field(default=None, ge=-90, le=90)
    pickup_longitude: float | None = Field(default=None, ge=-180, le=180)

    destination_latitude: float | None = Field(
        default=None, ge=-90, le=90
    )
    destination_longitude: float | None = Field(
        default=None, ge=-180, le=180
    )

    payment_method: PaymentMethod = "cash"

    price_rub: int | None = Field(default=None, ge=0)
    comment: str | None = None


# Ответ API с данными заказа
class OrderResponse(APIModel):
    id: int
    city_id: str
    customer_name: str | None
    customer_phone: str
    anonymous: bool

    pickup_address: str
    destination_address: str

    pickup_latitude: float | None
    pickup_longitude: float | None
    destination_latitude: float | None
    destination_longitude: float | None

    status: str
    payment_method: str
    price_rub: int | None
    driver_id: int | None
    comment: str | None

    created_at: datetime
    updated_at: datetime


# Авторизация диспетчера
class DispatcherLogin(APIModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=128)


# Ответ с токеном авторизации
class TokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"


# Данные диспетчера без пароля
class DispatcherResponse(APIModel):
    id: int
    username: str
    is_active: bool
    role: str
    created_at: datetime
