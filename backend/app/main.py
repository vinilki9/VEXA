
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Dispatcher, Order
from app.schemas import (
    DispatcherLogin,
    DispatcherResponse,
    OrderCreate,
    OrderResponse,
    TokenResponse,
)
from app.security import (
    create_access_token,
    get_current_dispatcher,
    verify_password,
)

app = FastAPI(title="VEXA API", version="0.3.0")

ACTIVE_CITIES = [
    {"city_id": "obolensk", "name": "Оболенск", "enabled": True}
]

ORDER_STATUSES = {
    "new": {"accepted", "cancelled"},
    "accepted": {"assigned", "cancelled"},
    "assigned": {"arrived", "cancelled"},
    "arrived": {"in_progress", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        )

    return {
        "status": "ok",
        "service": "vexa-api",
        "database": "connected",
        "utc": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/cities")
def list_cities():
    return {"cities": ACTIVE_CITIES}


@app.get("/api/v1/tariffs/{city_id}")
def get_tariffs(city_id: str):
    if city_id != settings.default_city_id or city_id != "obolensk":
        raise HTTPException(404, "City is not enabled")

    return {
        "city_id": city_id,
        "currency": "RUB",
        "configured": False,
        "tariffs": [],
    }


@app.post(
    "/api/v1/orders",
    response_model=OrderResponse,
    status_code=201,
)
def create_order(
    payload: OrderCreate,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
        max_length=128,
    ),
    db: Session = Depends(get_db),
):
    city_id = payload.city_id.strip()

    if city_id != settings.default_city_id or city_id != "obolensk":
        raise HTTPException(400, "City is not enabled")

    existing = db.scalar(
        select(Order).where(
            Order.city_id == city_id,
            Order.idempotency_key == idempotency_key,
        )
    )

    if existing:
        return existing

    order = Order(
        city_id=city_id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        anonymous=payload.anonymous,
        pickup_address=payload.pickup_address,
        destination_address=payload.destination_address,
        pickup_latitude=payload.pickup_latitude,
        pickup_longitude=payload.pickup_longitude,
        destination_latitude=payload.destination_latitude,
        destination_longitude=payload.destination_longitude,
        status="new",
        payment_method=payload.payment_method,
        price_rub=payload.price_rub,
        comment=payload.comment,
        idempotency_key=idempotency_key,
    )

    db.add(order)

    try:
        db.commit()
        db.refresh(order)
    except IntegrityError:
        db.rollback()

        existing = db.scalar(
            select(Order).where(
                Order.city_id == city_id,
                Order.idempotency_key == idempotency_key,
            )
        )

        if existing:
            return existing

        raise HTTPException(409, "Could not create order")

    return order


@app.post(
    "/api/v1/dispatch/auth/login",
    response_model=TokenResponse,
)
def dispatcher_login(
    payload: DispatcherLogin,
    db: Session = Depends(get_db),
):
    dispatcher = db.scalar(
        select(Dispatcher).where(
            Dispatcher.username == payload.username
        )
    )

    if (
        dispatcher is None
        or not dispatcher.is_active
        or not verify_password(
            payload.password,
            dispatcher.password_hash,
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Неверный логин или пароль",
        )

    return TokenResponse(
        access_token=create_access_token(dispatcher.id)
    )


@app.get(
    "/api/v1/dispatch/auth/me",
    response_model=DispatcherResponse,
)
def dispatcher_me(
    dispatcher: Dispatcher = Depends(get_current_dispatcher),
):
    return dispatcher


@app.get(
    "/api/v1/dispatch/orders",
    response_model=list[OrderResponse],
)
def list_orders(
    city_id: str = "obolensk",
    dispatcher: Dispatcher = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    if city_id != settings.default_city_id or city_id != "obolensk":
        raise HTTPException(404, "City is not enabled")

    return list(
        db.scalars(
            select(Order)
            .where(Order.city_id == city_id)
            .order_by(Order.created_at.desc())
        ).all()
    )


@app.patch(
    "/api/v1/dispatch/orders/{order_id}/status",
    response_model=OrderResponse,
)
def update_order_status(
    order_id: int,
    new_status: str,
    dispatcher: Dispatcher = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    order = db.get(Order, order_id)

    if order is None or order.city_id != "obolensk":
        raise HTTPException(404, "Order not found")

    allowed = ORDER_STATUSES.get(order.status, set())

    if new_status not in allowed:
        raise HTTPException(
            409,
            f"Invalid status transition: {order.status} -> {new_status}",
        )

    order.status = new_status
    order.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(order)

    return order
