
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import (
    Branch,
    City,
    CityOrderCounter,
    DispatcherProfile,
    Order,
    OrderStatusHistory,
    Tariff,
    User,
)
from app.schemas import (
    CityResponse,
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

app = FastAPI(title="VEXA API", version="0.4.0")


ORDER_STATUSES = {
    "new": {"accepted", "cancelled"},
    "accepted": {"assigned", "cancelled"},
    "assigned": {"arrived", "cancelled"},
    "arrived": {"in_progress", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

CITY_PREFIXES = {
    "obolensk": "OB",
}


def order_to_response(order: Order, city: City) -> dict:
    return {
        "id": order.id,
        "public_number": order.public_number,
        "city_id": order.city_id,
        "tariff_id": order.tariff_id,
        "branch_id": order.branch_id,
        "city_code": city.code,
        "passenger_user_id": order.passenger_user_id,
        "driver_user_id": order.driver_user_id,
        "vehicle_id": order.vehicle_id,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "anonymous": order.anonymous,
        "pickup_address": order.pickup_address,
        "destination_address": order.destination_address,
        "pickup_latitude": order.pickup_latitude,
        "pickup_longitude": order.pickup_longitude,
        "destination_latitude": order.destination_latitude,
        "destination_longitude": order.destination_longitude,
        "status": order.status,
        "payment_method": order.payment_method,
        "price_rub": order.price_rub,
        "price_kopecks": order.price_kopecks,
        "comment": order.comment,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }

def get_dispatcher_profile(
    db: Session,
    dispatcher: User,
) -> DispatcherProfile:
    profile = db.get(DispatcherProfile, dispatcher.id)

    if profile is None or not profile.is_active:
        raise HTTPException(403, "Доступ диспетчера запрещён")

    if profile.role == "dispatcher":
        if profile.branch_id is None:
            raise HTTPException(
                403,
                "Диспетчер не привязан к филиалу",
            )

        branch = db.get(Branch, profile.branch_id)

        if branch is None or not branch.is_active:
            raise HTTPException(
                403,
                "Филиал диспетчера неактивен или не найден",
            )

    elif profile.role != "chief_dispatcher":
        raise HTTPException(403, "Неизвестная роль диспетчера")

    return profile


def ensure_dispatcher_can_access_order(
    db: Session,
    dispatcher: User,
    order: Order,
) -> DispatcherProfile:
    profile = get_dispatcher_profile(db, dispatcher)

    if profile.role == "chief_dispatcher":
        return profile

    if profile.branch_id != order.branch_id:
        raise HTTPException(404, "Order not found")

    branch = db.get(Branch, order.branch_id)

    if (
        branch is None
        or not branch.is_active
        or branch.city_id != order.city_id
    ):
        raise HTTPException(404, "Order not found")

    return profile


def next_order_number(db: Session, city: City) -> str:
    dialect = db.bind.dialect.name

    values = {
        "city_id": city.id,
        "last_number": 1,
    }

    if dialect == "postgresql":
        statement = pg_insert(CityOrderCounter).values(**values)
    elif dialect == "sqlite":
        statement = sqlite_insert(CityOrderCounter).values(**values)
    else:
        raise RuntimeError("Unsupported database dialect for order counter")

    statement = statement.on_conflict_do_update(
        index_elements=[CityOrderCounter.city_id],
        set_={
            "last_number": CityOrderCounter.last_number + 1,
            "updated_at": func.now(),
        },
    ).returning(CityOrderCounter.last_number)

    number = db.scalar(statement)

    prefix = CITY_PREFIXES.get(city.code, city.code[:2].upper())

    return f"VEXA-{prefix}-{number:06d}"


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
def list_cities(db: Session = Depends(get_db)):
    cities = db.scalars(
        select(City)
        .where(City.is_active.is_(True))
        .order_by(City.name)
    ).all()

    return {
        "cities": [
            CityResponse.model_validate(city).model_dump(mode="json")
            for city in cities
        ]
    }


@app.get("/api/v1/tariffs/{city_code}")
def get_tariffs(
    city_code: str,
    db: Session = Depends(get_db),
):
    city = db.scalar(
        select(City).where(
            City.code == city_code,
            City.is_active.is_(True),
        )
    )

    if city is None:
        raise HTTPException(404, "City is not enabled")

    tariffs = db.scalars(
        select(Tariff)
        .where(
            Tariff.city_id == city.id,
            Tariff.is_active.is_(True),
        )
        .order_by(Tariff.name)
    ).all()

    return {
        "city_id": city.id,
        "city_code": city.code,
        "currency": "RUB",
        "configured": bool(tariffs),
        "tariffs": [
            {
                "id": tariff.id,
                "name": tariff.name,
                "vehicle_class": tariff.vehicle_class,
                "base_price_kopecks": tariff.base_price_kopecks,
                "price_per_km_kopecks": tariff.price_per_km_kopecks,
                "price_per_minute_kopecks": tariff.price_per_minute_kopecks,
            }
            for tariff in tariffs
        ],
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
    city = db.scalar(
        select(City).where(
            City.code == payload.city_code,
            City.is_active.is_(True),
        )
    )

    if city is None:
        raise HTTPException(400, "City is not enabled")
    if payload.tariff_id is None:
    raise HTTPException(
        status_code=400,
        detail="Перед созданием заказа необходимо выбрать тариф",
    )

selected_tariff = db.scalar(
    select(Tariff).where(
        Tariff.id == payload.tariff_id,
        Tariff.city_id == city.id,
        Tariff.is_active.is_(True),
    )
)

if selected_tariff is None:
    raise HTTPException(
        status_code=400,
        detail="Выбранный тариф не найден или неактивен",
    )
        )

        if selected_tariff is None:
            raise HTTPException(
                status_code=400,
                detail="Выбранный тариф не найден или неактивен",
            )
    existing = db.scalar(
        select(Order).where(
            Order.city_id == city.id,
            Order.idempotency_key == idempotency_key,
        )
    )

    if existing:
        return order_to_response(existing, city)
    branches = db.scalars(
        select(Branch).where(
            Branch.city_id == city.id,
            Branch.is_active.is_(True),
        )
    ).all()

    if not branches:
        raise HTTPException(
            status_code=503,
            detail="Для города не настроен активный филиал",
        )

    if len(branches) > 1:
        raise HTTPException(
            status_code=409,
            detail="Для города требуется настройка выбора филиала",
        )

    selected_branch = branches[0]

    is_anonymous = (
        payload.anonymous
        or not (payload.customer_name or "").strip()
    )

    order = Order(
        public_number=next_order_number(db, city),
        city_id=city.id,
        tariff_id=(selected_tariff.id
            if selected_tariff is not None
            else None
        ),
        branch_id=selected_branch.id,
        customer_name=(
            None
            if is_anonymous
            else payload.customer_name.strip()
        ),
        customer_phone=payload.customer_phone,
        anonymous=is_anonymous,
        pickup_address=payload.pickup_address,
        destination_address=payload.destination_address,
        pickup_latitude=payload.pickup_latitude,
        pickup_longitude=payload.pickup_longitude,
        destination_latitude=payload.destination_latitude,
        destination_longitude=payload.destination_longitude,
        status="new",
        payment_method=payload.payment_method,
        # Цена от клиента не считается доверенной.
        price_rub=None,
        price_kopecks=None,
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
                Order.city_id == city.id,
                Order.idempotency_key == idempotency_key,
            )
        )

        if existing:
            return order_to_response(existing, city)

        raise HTTPException(409, "Could not create order")

    return order_to_response(order, city)


@app.post(
    "/api/v1/dispatch/auth/login",
    response_model=TokenResponse,
)
def dispatcher_login(
    payload: DispatcherLogin,
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(User.username == payload.username)
    )

    if (
        user is None
        or not user.is_active
        or not user.password_hash
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=401,
            detail="Неверный логин или пароль",
        )

    profile = db.get(DispatcherProfile, user.id)

    if profile is None or not profile.is_active:
        raise HTTPException(
            status_code=401,
            detail="Неверный логин или пароль",
        )

    return TokenResponse(
        access_token=create_access_token(user.id)
    )


@app.get(
    "/api/v1/dispatch/auth/me",
    response_model=DispatcherResponse,
)

def dispatcher_me(
    user: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    profile = get_dispatcher_profile(db, user)

    return {
        "id": user.id,
        "username": user.username,
        "is_active": user.is_active and profile.is_active,
        "role": profile.role,
        "branch_id": profile.branch_id,
        "created_at": user.created_at,
    }



@app.get(
    "/api/v1/dispatch/orders",
    response_model=list[OrderResponse],
)

def list_orders(
    city_code: str = "obolensk",
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    profile = get_dispatcher_profile(db, dispatcher)

    query = select(Order).order_by(Order.created_at.desc())

    if profile.role == "dispatcher":
        query = query.where(
            Order.branch_id == profile.branch_id
        )
    elif profile.role == "chief_dispatcher":
        if city_code:
            city = db.scalar(
                select(City).where(
                    City.code == city_code,
                    City.is_active.is_(True),
                )
            )

            if city is None:
                raise HTTPException(404, "City is not enabled")

            query = query.where(Order.city_id == city.id)

    orders = db.scalars(query).all()

    result = []

    for order in orders:
        city = db.get(City, order.city_id)

        if city is not None:
            result.append(order_to_response(order, city))

    return result



@app.patch(
    "/api/v1/dispatch/orders/{order_id}/status",
    response_model=OrderResponse,
)

def update_order_status(
    order_id: UUID,
    new_status: str,
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    order = db.get(Order, order_id)

    if order is None:
        raise HTTPException(404, "Order not found")

    # Проверяем права до любого изменения заказа.
    ensure_dispatcher_can_access_order(
        db,
        dispatcher,
        order,
    )

    city = db.get(City, order.city_id)

    if city is None or not city.is_active:
        raise HTTPException(404, "Order not found")

    allowed = ORDER_STATUSES.get(order.status, set())

    if new_status not in allowed:
        raise HTTPException(
            409,
            f"Invalid status transition: {order.status} -> {new_status}",
        )

    old_status = order.status
    order.status = new_status
    order.updated_at = datetime.now(timezone.utc)

    db.add(
        OrderStatusHistory(
            order_id=order.id,
            old_status=old_status,
            new_status=new_status,
            changed_by_user_id=dispatcher.id,
        )
    )

    db.commit()
    db.refresh(order)

    return order_to_response(order, city)
