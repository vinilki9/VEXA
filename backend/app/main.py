from datetime import datetime, timezone
from uuid import UUID

from app.passenger_auth import router as passenger_auth_router
from app.driver_api import router as driver_router
from app.driver_transfer_api import router as driver_transfer_router
from app.phone_utils import normalize_phone

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.routing import RoutingError
from app.route_pricing import calculate_order_route_price

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
    TariffChangeHistory,
    User,
)
from app.schemas import (
    CityResponse,
    DispatcherLogin,
    DispatcherResponse,
    OrderCreate,
    OrderResponse,
    TokenResponse,
    TariffCreate,
    TariffUpdate,
)
from app.security import (
    create_access_token,
    get_current_dispatcher,
    get_current_passenger,
    verify_password,
)


app = FastAPI(title="VEXA API", version="0.6.0")
app.include_router(passenger_auth_router)
app.include_router(driver_router)
app.include_router(driver_transfer_router)


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


CARGO_VEHICLES = {
    "Универсал",
    "Каблук / небольшой фургон",
    "Средний грузовой фургон",
    "Газель",
}


# ============================================================
# COMMON HELPERS
# ============================================================

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
        "route_distance_meters": order.route_distance_meters,
        "route_duration_seconds": order.route_duration_seconds,
        "routing_provider": order.routing_provider,
        "status": order.status,
        "payment_method": order.payment_method,
        "price_rub": order.price_rub,
        "price_kopecks": order.price_kopecks,

        # Основная расшифровка стоимости.
        "fare_base_price_kopecks": (
            order.fare_base_price_kopecks
        ),
        "fare_distance_price_kopecks": (
            order.fare_distance_price_kopecks
        ),
        "fare_time_price_kopecks": (
            order.fare_time_price_kopecks
        ),
        "fare_limit_adjustment_kopecks": (
            order.fare_limit_adjustment_kopecks
        ),
        "anonymous_surcharge_kopecks": (
            order.anonymous_surcharge_kopecks
        ),

        # Выбранные дополнительные услуги.
        "child_seat": order.child_seat,
        "animal_transport": order.animal_transport,

        # Параметры грузового заказа.
        "cargo_vehicle": order.cargo_vehicle,
        "cargo_description": order.cargo_description,
        "cargo_loaders": order.cargo_loaders,

        # Снимок стоимости дополнительных услуг.
        "child_seat_surcharge_kopecks": (
            order.child_seat_surcharge_kopecks
        ),
        "animal_transport_surcharge_kopecks": (
            order.animal_transport_surcharge_kopecks
        ),
        "cargo_vehicle_surcharge_kopecks": (
            order.cargo_vehicle_surcharge_kopecks
        ),
        "cargo_loaders_surcharge_kopecks": (
            order.cargo_loaders_surcharge_kopecks
        ),

        "comment": order.comment,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


def is_cargo_tariff(tariff: Tariff) -> bool:
    """
    Определяет грузовой тариф по его коду,
    названию или классу автомобиля.
    """

    values = (
        tariff.code,
        tariff.name,
        tariff.vehicle_class,
    )

    for value in values:
        normalized = (value or "").strip().lower()

        if "cargo" in normalized or "груз" in normalized:
            return True

    return False


def get_dispatcher_profile(
    db: Session,
    dispatcher: User,
) -> DispatcherProfile:
    profile = db.get(DispatcherProfile, dispatcher.id)

    if profile is None or not profile.is_active:
        raise HTTPException(
            403,
            "Доступ диспетчера запрещён",
        )

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
        raise HTTPException(
            403,
            "Неизвестная роль диспетчера",
        )

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
        raise HTTPException(
            404,
            "Order not found",
        )

    branch = db.get(Branch, order.branch_id)

    if (
        branch is None
        or not branch.is_active
        or branch.city_id != order.city_id
    ):
        raise HTTPException(
            404,
            "Order not found",
        )

    return profile


# ============================================================
# TARIFF PERMISSIONS AND HISTORY
# ============================================================

def require_chief_dispatcher(
    db: Session,
    dispatcher: User,
) -> DispatcherProfile:
    profile = get_dispatcher_profile(db, dispatcher)

    if profile.role != "chief_dispatcher":
        raise HTTPException(
            403,
            "Изменять тарифы может только главный диспетчер",
        )

    return profile


def ensure_dispatcher_can_access_tariff(
    db: Session,
    dispatcher: User,
    tariff: Tariff,
) -> DispatcherProfile:
    profile = get_dispatcher_profile(db, dispatcher)

    if profile.role == "chief_dispatcher":
        return profile

    branch = db.get(Branch, profile.branch_id)

    if (
        branch is None
        or not branch.is_active
        or branch.city_id != tariff.city_id
    ):
        raise HTTPException(
            404,
            "Tariff not found",
        )

    return profile


def tariff_snapshot(tariff: Tariff) -> dict:
    """
    Полный снимок тарифа для неизменяемой истории.
    """

    return {
        "id": str(tariff.id),
        "city_id": str(tariff.city_id),
        "code": tariff.code,
        "name": tariff.name,
        "vehicle_class": tariff.vehicle_class,
        "base_price_kopecks": tariff.base_price_kopecks,
        "price_per_km_kopecks": (
            tariff.price_per_km_kopecks
        ),
        "price_per_minute_kopecks": (
            tariff.price_per_minute_kopecks
        ),
        "minimum_fare_kopecks": (
            tariff.minimum_fare_kopecks
        ),
        "maximum_fare_kopecks": (
            tariff.maximum_fare_kopecks
        ),
        "child_seat_surcharge_kopecks": (
            tariff.child_seat_surcharge_kopecks
        ),
        "animal_transport_surcharge_kopecks": (
            tariff.animal_transport_surcharge_kopecks
        ),
        "cargo_vehicle_surcharges": (
            tariff.cargo_vehicle_surcharges or {}
        ),
        "cargo_loader_price_per_person_kopecks": (
            tariff.cargo_loader_price_per_person_kopecks
        ),
        "is_active": tariff.is_active,
    }


# ============================================================
# ORDER NUMBER GENERATION
# ============================================================

def next_order_number(db: Session, city: City) -> str:
    dialect = db.bind.dialect.name

    values = {
        "city_id": city.id,
        "last_number": 1,
    }

    if dialect == "postgresql":
        statement = pg_insert(
            CityOrderCounter
        ).values(**values)

    elif dialect == "sqlite":
        statement = sqlite_insert(
            CityOrderCounter
        ).values(**values)

    else:
        raise RuntimeError(
            "Unsupported database dialect for order counter"
        )

    statement = statement.on_conflict_do_update(
        index_elements=[CityOrderCounter.city_id],
        set_={
            "last_number": (
                CityOrderCounter.last_number + 1
            ),
            "updated_at": func.now(),
        },
    ).returning(
        CityOrderCounter.last_number
    )

    number = db.scalar(statement)

    prefix = CITY_PREFIXES.get(
        city.code,
        city.code[:2].upper(),
    )

    return f"VEXA-{prefix}-{number:06d}"


# ============================================================
# HEALTH
# ============================================================

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


# ============================================================
# CITIES
# ============================================================

@app.get("/api/v1/cities")
def list_cities(
    db: Session = Depends(get_db),
):
    cities = db.scalars(
        select(City)
        .where(City.is_active.is_(True))
        .order_by(City.name)
    ).all()

    return {
        "cities": [
            CityResponse.model_validate(
                city
            ).model_dump(mode="json")
            for city in cities
        ]
    }


# ============================================================
# PUBLIC TARIFFS
# ============================================================

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
        raise HTTPException(
            404,
            "City is not enabled",
        )

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
                "code": tariff.code,
                "name": tariff.name,
                "vehicle_class": tariff.vehicle_class,
                "base_price_kopecks": (
                    tariff.base_price_kopecks
                ),
                "price_per_km_kopecks": (
                    tariff.price_per_km_kopecks
                ),
                "price_per_minute_kopecks": (
                    tariff.price_per_minute_kopecks
                ),
                "minimum_fare_kopecks": (
                    tariff.minimum_fare_kopecks
                ),
                "maximum_fare_kopecks": (
                    tariff.maximum_fare_kopecks
                ),
                "child_seat_surcharge_kopecks": (
                    tariff.child_seat_surcharge_kopecks
                ),
                "animal_transport_surcharge_kopecks": (
                    tariff.animal_transport_surcharge_kopecks
                ),
                "cargo_vehicle_surcharges": (
                    tariff.cargo_vehicle_surcharges or {}
                ),
                "cargo_loader_price_per_person_kopecks": (
                    tariff.cargo_loader_price_per_person_kopecks
                ),
            }
            for tariff in tariffs
        ],
    }


# ============================================================
# DISPATCHER TARIFF MANAGEMENT
# ============================================================

@app.get("/api/v1/dispatch/tariffs")
def list_dispatch_tariffs(
    city_code: str | None = None,
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    profile = get_dispatcher_profile(
        db,
        dispatcher,
    )

    query = (
        select(Tariff)
        .join(
            City,
            City.id == Tariff.city_id,
        )
        .where(
            City.is_active.is_(True)
        )
    )

    if profile.role == "dispatcher":
        branch = db.get(
            Branch,
            profile.branch_id,
        )

        if branch is None or not branch.is_active:
            raise HTTPException(
                403,
                "Филиал недоступен",
            )

        if city_code:
            city = db.get(
                City,
                branch.city_id,
            )

            if city is None or city.code != city_code:
                raise HTTPException(
                    404,
                    "City not found",
                )

        query = query.where(
            Tariff.city_id == branch.city_id
        )

    elif city_code:
        city = db.scalar(
            select(City).where(
                City.code == city_code,
                City.is_active.is_(True),
            )
        )

        if city is None:
            raise HTTPException(
                404,
                "City not found",
            )

        query = query.where(
            Tariff.city_id == city.id
        )

    tariffs = db.scalars(
        query.order_by(
            Tariff.city_id,
            Tariff.name,
        )
    ).all()

    return {
        "tariffs": [
            tariff_snapshot(tariff)
            for tariff in tariffs
        ]
    }


@app.post(
    "/api/v1/dispatch/tariffs",
    status_code=201,
)
def create_tariff(
    payload: TariffCreate,
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    require_chief_dispatcher(
        db,
        dispatcher,
    )

    city = db.scalar(
        select(City).where(
            City.code == payload.city_code,
            City.is_active.is_(True),
        )
    )

    if city is None:
        raise HTTPException(
            404,
            "City not found",
        )

    if (
        payload.minimum_fare_kopecks is not None
        and payload.maximum_fare_kopecks is not None
        and payload.maximum_fare_kopecks
        < payload.minimum_fare_kopecks
    ):
        raise HTTPException(
            422,
            "Максимальная стоимость меньше минимальной",
        )

    data = payload.model_dump(
        exclude={"city_code"}
    )

    tariff = Tariff(
        city_id=city.id,
        **data,
    )

    db.add(tariff)

    try:
        db.flush()

        db.add(
            TariffChangeHistory(
                tariff_id=tariff.id,
                city_id=city.id,
                changed_by_user_id=dispatcher.id,
                action="created",
                old_values=None,
                new_values=tariff_snapshot(tariff),
            )
        )

        db.commit()
        db.refresh(tariff)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            409,
            "Тариф с таким кодом уже существует в городе",
        )

    return tariff_snapshot(tariff)


@app.patch(
    "/api/v1/dispatch/tariffs/{tariff_id}"
)
def update_tariff(
    tariff_id: UUID,
    payload: TariffUpdate,
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    require_chief_dispatcher(
        db,
        dispatcher,
    )

    tariff = db.get(
        Tariff,
        tariff_id,
    )

    if tariff is None:
        raise HTTPException(
            404,
            "Tariff not found",
        )

    old_values = tariff_snapshot(tariff)

    changes = payload.model_dump(
        exclude_unset=True
    )

    if not changes:
        raise HTTPException(
            400,
            "Нет данных для изменения",
        )

    required_fields = {
        "code",
        "name",
        "vehicle_class",
        "base_price_kopecks",
        "price_per_km_kopecks",
        "price_per_minute_kopecks",
        "is_active",
    }

    for field in required_fields:
        if field in changes and changes[field] is None:
            raise HTTPException(
                422,
                f"Поле {field} не может быть пустым",
            )

    for field, value in changes.items():
        setattr(
            tariff,
            field,
            value,
        )

    if (
        tariff.minimum_fare_kopecks is not None
        and tariff.maximum_fare_kopecks is not None
        and tariff.maximum_fare_kopecks
        < tariff.minimum_fare_kopecks
    ):
        db.rollback()

        raise HTTPException(
            422,
            "Максимальная стоимость меньше минимальной",
        )

    new_values = tariff_snapshot(tariff)

    db.add(
        TariffChangeHistory(
            tariff_id=tariff.id,
            city_id=tariff.city_id,
            changed_by_user_id=dispatcher.id,
            action="updated",
            old_values=old_values,
            new_values=new_values,
        )
    )

    try:
        db.commit()
        db.refresh(tariff)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            409,
            "Не удалось сохранить изменения тарифа",
        )

    return tariff_snapshot(tariff)


@app.get(
    "/api/v1/dispatch/tariffs/{tariff_id}/history"
)
def get_tariff_history(
    tariff_id: UUID,
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    tariff = db.get(
        Tariff,
        tariff_id,
    )

    if tariff is None:
        raise HTTPException(
            404,
            "Tariff not found",
        )

    ensure_dispatcher_can_access_tariff(
        db,
        dispatcher,
        tariff,
    )

    rows = db.execute(
        select(
            TariffChangeHistory,
            User.username,
        )
        .join(
            User,
            User.id == TariffChangeHistory.changed_by_user_id,
        )
        .where(
            TariffChangeHistory.tariff_id == tariff.id,
            TariffChangeHistory.city_id == tariff.city_id,
        )
        .order_by(
            TariffChangeHistory.changed_at.desc(),
            TariffChangeHistory.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()

    return {
        "tariff_id": str(tariff.id),
        "history": [
            {
                "id": str(history.id),
                "action": history.action,
                "changed_by_user_id": str(
                    history.changed_by_user_id
                ),
                "changed_by_username": username,
                "old_values": history.old_values,
                "new_values": history.new_values,
                "changed_at": history.changed_at,
            }
            for history, username in rows
        ],
    }


# ============================================================
# CREATE ORDER
# ============================================================

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
    passenger: User = Depends(get_current_passenger),
    db: Session = Depends(get_db),
):
    if not passenger.phone:
        raise HTTPException(
            403,
            "У аккаунта пассажира не подтверждён номер телефона",
        )

    request_phone = normalize_phone(
        payload.customer_phone
    )

    if request_phone != passenger.phone:
        raise HTTPException(
            403,
            "Номер заказа не совпадает с подтверждённым номером аккаунта",
        )

    city = db.scalar(
        select(City).where(
            City.code == payload.city_code,
            City.is_active.is_(True),
        )
    )

    if city is None:
        raise HTTPException(
            400,
            "City is not enabled",
        )

    # Защита от повторного создания одного заказа.
    existing = db.scalar(
        select(Order).where(
            Order.city_id == city.id,
            Order.idempotency_key == idempotency_key,
        )
    )

    if existing is not None:
        if existing.passenger_user_id != passenger.id:
            raise HTTPException(
                404,
                "Заказ не найден",
            )

        return order_to_response(
            existing,
            city,
        )

    if payload.tariff_id is None:
        raise HTTPException(
            400,
            "Необходимо выбрать тариф",
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
            400,
            "Выбранный тариф не найден или неактивен",
        )

    # Для города должен быть настроен активный филиал.
    branches = db.scalars(
        select(Branch).where(
            Branch.city_id == city.id,
            Branch.is_active.is_(True),
        )
    ).all()

    if not branches:
        raise HTTPException(
            503,
            "Для города не настроен активный филиал",
        )

    if len(branches) > 1:
        raise HTTPException(
            409,
            "Для города требуется настройка выбора филиала",
        )

    selected_branch = branches[0]

    # Если имя не указано, заказ считается анонимным.
    is_anonymous = (
        payload.anonymous
        or not (payload.customer_name or "").strip()
    )

    cargo_order = is_cargo_tariff(
        selected_tariff
    )

    # Проверка совместимости параметров заказа с тарифом.
    if cargo_order:
        if payload.child_seat or payload.animal_transport:
            raise HTTPException(
                422,
                "Детское кресло и перевозка животного "
                "не применяются к грузовому тарифу",
            )

        if payload.cargo_vehicle is None:
            raise HTTPException(
                422,
                "Для грузового заказа необходимо выбрать автомобиль",
            )

        if payload.cargo_vehicle not in CARGO_VEHICLES:
            raise HTTPException(
                422,
                "Недопустимый тип грузового автомобиля",
            )

    else:
        if (
            payload.cargo_vehicle is not None
            or (payload.cargo_description or "").strip()
            or payload.cargo_loaders > 0
        ):
            raise HTTPException(
                422,
                "Параметры грузового заказа доступны "
                "только для грузового тарифа",
            )

    coordinates = (
        payload.pickup_latitude,
        payload.pickup_longitude,
        payload.destination_latitude,
        payload.destination_longitude,
    )

    if any(value is None for value in coordinates):
        raise HTTPException(
            400,
            (
                "Для расчёта стоимости необходимы координаты "
                "подачи и назначения"
            ),
        )

    try:
        route_pricing = calculate_order_route_price(
            pickup_latitude=payload.pickup_latitude,
            pickup_longitude=payload.pickup_longitude,
            destination_latitude=payload.destination_latitude,
            destination_longitude=payload.destination_longitude,
            base_price_kopecks=(
                selected_tariff.base_price_kopecks
            ),
            price_per_km_kopecks=(
                selected_tariff.price_per_km_kopecks
            ),
            price_per_minute_kopecks=(
                selected_tariff.price_per_minute_kopecks
            ),
            anonymous=is_anonymous,
            minimum_fare_kopecks=(
                selected_tariff.minimum_fare_kopecks
            ),
            maximum_fare_kopecks=(
                selected_tariff.maximum_fare_kopecks
            ),
        )

    except RoutingError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Не удалось рассчитать маршрут. "
                "Попробуйте позже."
            ),
        ) from exc

    # Базовая стоимость маршрута уже содержит:
    # базовую цену, расстояние, время, ограничения тарифа
    # и анонимную доплату.
    fare = route_pricing.fare

    # Все дополнительные суммы берутся только из тарифа сервера.
    child_seat_surcharge = (
        selected_tariff.child_seat_surcharge_kopecks
        if payload.child_seat
        else 0
    )

    animal_transport_surcharge = (
        selected_tariff.animal_transport_surcharge_kopecks
        if payload.animal_transport
        else 0
    )

    cargo_vehicle_surcharge = 0

    if cargo_order:
        cargo_prices = (
            selected_tariff.cargo_vehicle_surcharges or {}
        )

        cargo_vehicle_surcharge = cargo_prices.get(
            payload.cargo_vehicle,
            0,
        )

    cargo_loaders_surcharge = (
        payload.cargo_loaders
        * selected_tariff.cargo_loader_price_per_person_kopecks
    )

    # Итоговая стоимость рассчитывается исключительно сервером.
    total_kopecks = (
        fare.total_price_kopecks
        + child_seat_surcharge
        + animal_transport_surcharge
        + cargo_vehicle_surcharge
        + cargo_loaders_surcharge
    )

    route_distance_meters = int(
        route_pricing.route.distance_meters.to_integral_value()
    )

    route_duration_seconds = int(
        route_pricing.route.duration_seconds.to_integral_value()
    )

    total_rubles = (
        total_kopecks + 50
    ) // 100

    order = Order(
        public_number=next_order_number(
            db,
            city,
        ),
        city_id=city.id,
        tariff_id=selected_tariff.id,
        branch_id=selected_branch.id,
        passenger_user_id=passenger.id,

        customer_name=(
            None
            if is_anonymous
            else payload.customer_name.strip()
        ),
        customer_phone=passenger.phone,
        anonymous=is_anonymous,

        pickup_address=payload.pickup_address,
        destination_address=payload.destination_address,

        pickup_latitude=payload.pickup_latitude,
        pickup_longitude=payload.pickup_longitude,
        destination_latitude=payload.destination_latitude,
        destination_longitude=payload.destination_longitude,

        route_distance_meters=route_distance_meters,
        route_duration_seconds=route_duration_seconds,
        routing_provider=route_pricing.provider_name,

        status="new",
        payment_method=payload.payment_method,

        price_rub=total_rubles,
        price_kopecks=total_kopecks,

        # Основная расшифровка маршрута.
        fare_base_price_kopecks=(
            fare.base_price_kopecks
        ),
        fare_distance_price_kopecks=(
            fare.distance_price_kopecks
        ),
        fare_time_price_kopecks=(
            fare.time_price_kopecks
        ),
        fare_limit_adjustment_kopecks=(
            fare.fare_limit_adjustment_kopecks
        ),
        anonymous_surcharge_kopecks=(
            fare.anonymous_surcharge_kopecks
        ),

        # Выбранные дополнительные услуги.
        child_seat=payload.child_seat,
        animal_transport=payload.animal_transport,

        # Параметры грузового заказа.
        cargo_vehicle=(
            payload.cargo_vehicle
            if cargo_order
            else None
        ),
        cargo_description=(
            payload.cargo_description
            if cargo_order
            else None
        ),
        cargo_loaders=(
            payload.cargo_loaders
            if cargo_order
            else 0
        ),

        # Фиксируем суммы дополнительных услуг.
        # Изменение тарифа в будущем не повлияет на этот заказ.
        child_seat_surcharge_kopecks=(
            child_seat_surcharge
        ),
        animal_transport_surcharge_kopecks=(
            animal_transport_surcharge
        ),
        cargo_vehicle_surcharge_kopecks=(
            cargo_vehicle_surcharge
        ),
        cargo_loaders_surcharge_kopecks=(
            cargo_loaders_surcharge
        ),

        comment=payload.comment,
        idempotency_key=idempotency_key,
    )

    db.add(order)

    try:
        db.commit()
        db.refresh(order)

    except IntegrityError:
        db.rollback()

        # Повторная проверка нужна на случай одновременных запросов
        # с одним и тем же ключом идемпотентности.
        existing = db.scalar(
            select(Order).where(
                Order.city_id == city.id,
                Order.idempotency_key == idempotency_key,
            )
        )

        if existing is not None:
            if existing.passenger_user_id != passenger.id:
                raise HTTPException(
                    404,
                    "Заказ не найден",
                )

            return order_to_response(
                existing,
                city,
            )

        raise HTTPException(
            409,
            "Не удалось создать заказ",
        )

    return order_to_response(
        order,
        city,
    )


# ============================================================
# DISPATCHER AUTHENTICATION
# ============================================================

@app.post(
    "/api/v1/dispatch/auth/login",
    response_model=TokenResponse,
)
def dispatcher_login(
    payload: DispatcherLogin,
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(
            User.username == payload.username
        )
    )

    if (
        user is None
        or not user.is_active
        or not user.password_hash
        or not verify_password(
            payload.password,
            user.password_hash,
        )
    ):
        raise HTTPException(
            401,
            "Неверный логин или пароль",
        )

    profile = db.get(
        DispatcherProfile,
        user.id,
    )

    if profile is None or not profile.is_active:
        raise HTTPException(
            401,
            "Неверный логин или пароль",
        )

    return TokenResponse(
        access_token=create_access_token(
            user.id
        )
    )


@app.get(
    "/api/v1/dispatch/auth/me",
    response_model=DispatcherResponse,
)
def dispatcher_me(
    user: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    profile = get_dispatcher_profile(
        db,
        user,
    )

    return {
        "id": user.id,
        "username": user.username,
        "is_active": (
            user.is_active and profile.is_active
        ),
        "role": profile.role,
        "branch_id": profile.branch_id,
        "created_at": user.created_at,
    }


# ============================================================
# PASSENGER ORDER HISTORY
# ============================================================

@app.get(
    "/api/v1/passenger/orders",
    response_model=list[OrderResponse],
)
def list_passenger_orders(
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    passenger: User = Depends(get_current_passenger),
    db: Session = Depends(get_db),
):
    orders = db.scalars(
        select(Order)
        .where(
            Order.passenger_user_id == passenger.id
        )
        .order_by(
            Order.created_at.desc()
        )
        .limit(limit)
        .offset(offset)
    ).all()

    result = []

    for order in orders:
        city = db.get(
            City,
            order.city_id,
        )

        if city is not None:
            result.append(
                order_to_response(
                    order,
                    city,
                )
            )

    return result


# ============================================================
# DISPATCHER ORDERS
# ============================================================

@app.get(
    "/api/v1/dispatch/orders",
    response_model=list[OrderResponse],
)
def list_orders(
    city_code: str = "obolensk",
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    profile = get_dispatcher_profile(
        db,
        dispatcher,
    )

    query = select(Order).order_by(
        Order.created_at.desc()
    )

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
                raise HTTPException(
                    404,
                    "City is not enabled",
                )

            query = query.where(
                Order.city_id == city.id
            )

    orders = db.scalars(query).all()

    result = []

    for order in orders:
        city = db.get(
            City,
            order.city_id,
        )

        if city is not None:
            result.append(
                order_to_response(
                    order,
                    city,
                )
            )

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
    order = db.get(
        Order,
        order_id,
    )

    if order is None:
        raise HTTPException(
            404,
            "Order not found",
        )

    ensure_dispatcher_can_access_order(
        db,
        dispatcher,
        order,
    )

    city = db.get(
        City,
        order.city_id,
    )

    if city is None or not city.is_active:
        raise HTTPException(
            404,
            "Order not found",
        )

    allowed = ORDER_STATUSES.get(
        order.status,
        set(),
    )

    if new_status not in allowed:
        raise HTTPException(
            409,
            (
                f"Invalid status transition: "
                f"{order.status} -> {new_status}"
            ),
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

    return order_to_response(
        order,
        city,
    )
