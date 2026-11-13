from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class LoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=200)

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class DispatcherOut(BaseModel):
    id: int
    username: str
    role: str
    model_config = ConfigDict(from_attributes=True)

class OrderCreate(BaseModel):
    city_id: str = "obolensk"
    customer_name: str = Field(min_length=1, max_length=120)
    customer_phone: str = Field(min_length=5, max_length=40)
    pickup_address: str = Field(min_length=3, max_length=500)
    destination_address: str = Field(min_length=3, max_length=500)
    payment_method: str = "cash"
    price_rub: int | None = Field(default=None, ge=0)
    comment: str | None = Field(default=None, max_length=2000)

class OrderStatusUpdate(BaseModel):
    status: str = Field(min_length=2, max_length=40)

class OrderOut(BaseModel):
    id: int
    city_id: str
    customer_name: str
    customer_phone: str
    pickup_address: str
    destination_address: str
    status: str
    payment_method: str
    price_rub: int | None
    driver_id: int | None
    comment: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
