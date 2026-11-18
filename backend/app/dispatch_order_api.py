
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.driver_order_offer_models import DriverOrderOffer
from app.models import (
    Branch,
    City,
    DispatcherProfile,
    DriverLocation,
    DriverProfile,
    Order,
    OrderStatusHistory,
    User,
    Vehicle,
)
from app.security import get_current_dispatcher


router = APIRouter(
    prefix="/api/v1/dispatch",
    tags=["Dispatcher Orders"],
)

ACTIVE_ORDER_STATUSES = (
    "assigned",
    "arrived",
    "in_progress",
)

OFFER_RESPONSE_TIMEOUT_SECONDS = 13

GPS_MAX_AGE = timedelta(minutes=10)
GPS_FUTURE_TOLERANCE = timedelta(minutes=1)

NO_AVAILABLE_DRIVERS_MESSAGE = (
    "Нет свободных водителей с актуальным GPS и подходящим автомобилем"
)


class AssignDriverRequest(BaseModel):
    driver_user_id: UUID
    vehicle_id: UUID


def get_dispatcher_profile(
    db: Session,
    dispatcher: User,
) -> DispatcherProfile:
    profile = db.get(
        DispatcherProfile,
        dispatcher.id,
    )

    if profile is None or not profile.is_active:
        raise HTTPException(
            403,
            "Доступ диспетчера запрещён",
        )

    if profile.role == "dispatcher":
        if profile.branch_id is None:
            raise HTTPException(
                403,
                "Диспетчер не привязан к таксопарку",
            )

        branch = db.get(
            Branch,
            profile.branch_id,
        )

        if branch is None or not branch.is_active:
            raise HTTPException(
                403,
                "Таксопарк диспетчера недоступен",
            )

    elif profile.role != "chief_dispatcher":
        raise HTTPException(
            403,
            "Неизвестная роль диспетчера",
        )

    return profile


def ensure_order_access(
    profile: DispatcherProfile,
    order: Order,
) -> None:
    if profile.role == "dispatcher":
        if order.branch_id != profile.branch_id:
            raise HTTPException(
                404,
                "Заказ не найден",
            )


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def calculate_distance_meters(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    earth_radius_meters = 6_371_000

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)

    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1_rad)
        * cos(lat2_rad)
        * sin(delta_lon / 2) ** 2
    )

    return (
        2
        * earth_radius_meters
        * asin(sqrt(min(1.0, a)))
    )


def validate_order_for_assignment(
    db: Session,
    order: Order,
) -> City:
    city = db.get(
        City,
        order.city_id,
    )

    if city is None or not city.is_active:
        raise HTTPException(
            409,
            "Город заказа недоступен",
        )

    if order.status != "accepted":
        raise HTTPException(
            409,
            "Заказ должен иметь статус accepted",
        )

    if order.driver_user_id is not None:
        raise HTTPException(
            409,
            "К заказу уже назначен водитель",
        )

    return city


def get_busy_driver_ids(
    db: Session,
) -> set[UUID]:
    rows = db.scalars(
        select(Order.driver_user_id).where(
            Order.driver_user_id.is_not(None),
            Order.status.in_(ACTIVE_ORDER_STATUSES),
        )
    ).all()

    return set(rows)


def get_eligible_branch_condition(
    order: Order,
):
    """
    Водители соответствующего таксопарка и самостоятельные
    водители участвуют в распределении на равных условиях.

    Водители других таксопарков не допускаются.
    """
    return or_(
        DriverProfile.branch_id == order.branch_id,
        DriverProfile.branch_id.is_(None),
    )


def get_available_driver_candidates(
    db: Session,
    order: Order,
    excluded_driver_ids: set[UUID] | None = None,
) -> list[tuple]:
    if (
        order.pickup_latitude is None
        or order.pickup_longitude is None
    ):
        raise HTTPException(
            409,
            "У заказа отсутствуют GPS-координаты подачи",
        )

    now = datetime.now(timezone.utc)
    oldest_allowed = now - GPS_MAX_AGE
    newest_allowed = now + GPS_FUTURE_TOLERANCE

    busy_driver_ids = get_busy_driver_ids(db)

    excluded_driver_ids = excluded_driver_ids or set()

    pending_rows = db.scalars(
        select(DriverOrderOffer.driver_user_id).where(
            DriverOrderOffer.status == "pending",
            DriverOrderOffer.expires_at > now,
        )
    ).all()

    drivers_with_pending_offers = set(pending_rows)

    driver_profiles = db.scalars(
        select(DriverProfile).where(
            DriverProfile.is_active.is_(True),
            DriverProfile.is_online.is_(True),
            DriverProfile.city_id == order.city_id,
            get_eligible_branch_condition(order),
        )
    ).all()

    candidates = []

    for driver_profile in driver_profiles:
        driver_id = driver_profile.user_id

        if driver_id in busy_driver_ids:
            continue

        if driver_id in excluded_driver_ids:
            continue

        if driver_id in drivers_with_pending_offers:
            continue

        driver_user = db.get(
            User,
            driver_id,
        )

        if driver_user is None or not driver_user.is_active:
            continue

        location = db.get(
            DriverLocation,
            driver_id,
        )

        if location is None:
            continue

        recorded_at = normalize_datetime(
            location.recorded_at
        )

        if recorded_at < oldest_allowed:
            continue

        if recorded_at > newest_allowed:
            continue

        vehicles = db.scalars(
            select(Vehicle)
            .where(
                Vehicle.driver_user_id == driver_id,
                Vehicle.city_id == order.city_id,
                Vehicle.is_active.is_(True),
            )
            .order_by(Vehicle.id)
        ).all()

        if not vehicles:
            continue

        vehicle = vehicles[0]

        distance = calculate_distance_meters(
            order.pickup_latitude,
            order.pickup_longitude,
            location.latitude,
            location.longitude,
        )

        rating = float(driver_profile.rating or 0)

        candidates.append(
            (
                distance,
                -rating,
                str(driver_id),
                driver_profile,
                vehicle,
            )
        )

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        )
    )

    return candidates


def create_next_driver_offer(
    db: Session,
    order: Order,
) -> dict:
    """
    Создаёт следующее предложение заказа.

    Если действующее предложение уже существует,
    повторно его не создаёт.

    Истёкшие предложения переводятся в expired.
    Водители, которым заказ уже предлагался, повторно
    в рамках этого заказа не выбираются.
    """
    now = datetime.now(timezone.utc)

    pending_offer = db.scalar(
        select(DriverOrderOffer)
        .where(
            DriverOrderOffer.order_id == order.id,
            DriverOrderOffer.status == "pending",
        )
        .with_for_update()
    )

    if pending_offer is not None:
        expires_at = normalize_datetime(
            pending_offer.expires_at
        )

        if expires_at > now:
            return {
                "success": True,
                "offered": True,
                "offer_id": str(pending_offer.id),
                "order_id": str(order.id),
                "driver_user_id": str(
                    pending_offer.driver_user_id
                ),
                "vehicle_id": str(
                    pending_offer.vehicle_id
                ),
                "attempt_number": pending_offer.attempt_number,
                "response_timeout_seconds": (
                    pending_offer.response_timeout_seconds
                ),
                "expires_at": pending_offer.expires_at,
                "distance_to_pickup_meters": (
                    pending_offer.distance_meters
                ),
                "message": (
                    "Предложение заказа уже ожидает ответа водителя"
                ),
            }

        pending_offer.status = "expired"
        pending_offer.responded_at = now

    if order.status != "accepted":
        raise HTTPException(
            409,
            "Предлагать можно только принятый заказ",
        )

    if order.driver_user_id is not None:
        raise HTTPException(
            409,
            "К заказу уже назначен водитель",
        )

    previous_offers = db.scalars(
        select(DriverOrderOffer.driver_user_id).where(
            DriverOrderOffer.order_id == order.id,
        )
    ).all()

    excluded_driver_ids = set(previous_offers)

    candidates = get_available_driver_candidates(
        db=db,
        order=order,
        excluded_driver_ids=excluded_driver_ids,
    )

    if not candidates:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        raise HTTPException(
            409,
            NO_AVAILABLE_DRIVERS_MESSAGE,
        )

    distance, _, _, selected_driver, selected_vehicle = (
        candidates[0]
    )

    attempt_number = len(previous_offers) + 1

    offer = DriverOrderOffer(
        order_id=order.id,
        driver_user_id=selected_driver.user_id,
        vehicle_id=selected_vehicle.id,
        status="pending",
        attempt_number=attempt_number,
        response_timeout_seconds=(
            OFFER_RESPONSE_TIMEOUT_SECONDS
        ),
        distance_meters=int(round(distance)),
        offered_at=now,
        expires_at=(
            now
            + timedelta(
                seconds=OFFER_RESPONSE_TIMEOUT_SECONDS
            )
        ),
    )

    db.add(offer)

    try:
        db.commit()
        db.refresh(offer)
    except Exception:
        db.rollback()
        raise

    return {
        "success": True,
        "offered": True,
        "offer_id": str(offer.id),
        "order_id": str(order.id),
        "public_number": order.public_number,
        "status": order.status,
        "driver_user_id": str(offer.driver_user_id),
        "vehicle_id": str(offer.vehicle_id),
        "attempt_number": offer.attempt_number,
        "response_timeout_seconds": (
            offer.response_timeout_seconds
        ),
        "expires_at": offer.expires_at,
        "distance_to_pickup_meters": (
            offer.distance_meters
        ),
        "city_code": db.get(City, order.city_id).code,
        "message": (
            "Предложение заказа отправлено водителю"
        ),
    }


def save_driver_assignment(
    db: Session,
    order: Order,
    driver_profile: DriverProfile,
    vehicle: Vehicle,
    dispatcher: User,
    city: City,
    distance_meters: float | None = None,
) -> dict:
    old_status = order.status
    now = datetime.now(timezone.utc)

    pending_offers = db.scalars(
        select(DriverOrderOffer)
        .where(
            DriverOrderOffer.order_id == order.id,
            DriverOrderOffer.status == "pending",
        )
        .with_for_update()
    ).all()

    for offer in pending_offers:
        offer.status = "cancelled"
        offer.responded_at = now

    order.driver_user_id = driver_profile.user_id
    order.vehicle_id = vehicle.id
    order.status = "assigned"
    order.updated_at = now

    db.add(
        OrderStatusHistory(
            order_id=order.id,
            old_status=old_status,
            new_status="assigned",
            changed_by_user_id=dispatcher.id,
        )
    )

    try:
        db.commit()
        db.refresh(order)

    except Exception:
        db.rollback()
        raise

    result = {
        "success": True,
        "message": "Водитель назначен на заказ",
        "order_id": str(order.id),
        "public_number": order.public_number,
        "status": order.status,
        "driver_user_id": str(order.driver_user_id),
        "vehicle_id": str(order.vehicle_id),
        "city_code": city.code,
    }

    if distance_meters is not None:
        result["distance_to_pickup_meters"] = round(
            distance_meters
        )

    return result


@router.get("/orders/{order_id}/available-drivers")
def list_available_drivers_for_order(
    order_id: UUID,
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    profile = get_dispatcher_profile(
        db,
        dispatcher,
    )

    order = db.get(
        Order,
        order_id,
    )

    if order is None:
        raise HTTPException(
            404,
            "Заказ не найден",
        )

    ensure_order_access(profile, order)

    if order.status != "accepted":
        raise HTTPException(
            409,
            "Список водителей доступен для принятого заказа",
        )

    if order.driver_user_id is not None:
        raise HTTPException(
            409,
            "К заказу уже назначен водитель",
        )

    city = db.get(
        City,
        order.city_id,
    )

    if city is None or not city.is_active:
        raise HTTPException(
            409,
            "Город заказа недоступен",
        )

    busy_driver_ids = get_busy_driver_ids(db)

    driver_profiles = db.scalars(
        select(DriverProfile).where(
            DriverProfile.is_active.is_(True),
            DriverProfile.is_online.is_(True),
            DriverProfile.city_id == order.city_id,
            get_eligible_branch_condition(order),
        )
    ).all()

    drivers = []

    for driver_profile in driver_profiles:
        driver_id = driver_profile.user_id

        if driver_id in busy_driver_ids:
            continue

        driver_user = db.get(
            User,
            driver_id,
        )

        if driver_user is None or not driver_user.is_active:
            continue

        vehicles = db.scalars(
            select(Vehicle)
            .where(
                Vehicle.driver_user_id == driver_id,
                Vehicle.city_id == order.city_id,
                Vehicle.is_active.is_(True),
            )
            .order_by(Vehicle.id)
        ).all()

        for vehicle in vehicles:
            location = db.get(
                DriverLocation,
                driver_id,
            )

            drivers.append(
                {
                    "driver_user_id": str(driver_id),
                    "username": driver_user.username,
                    "phone": driver_user.phone,
                    "rating": str(driver_profile.rating),
                    "is_online": driver_profile.is_online,
                    "location": (
                        {
                            "latitude": location.latitude,
                            "longitude": location.longitude,
                            "recorded_at": location.recorded_at,
                        }
                        if location is not None
                        else None
                    ),
                    "vehicle": {
                        "id": str(vehicle.id),
                        "make": vehicle.make,
                        "model": vehicle.model,
                        "color": vehicle.color,
                        "license_plate": vehicle.license_plate,
                    },
                }
            )

    drivers.sort(
        key=lambda item: (
            -float(item["rating"]),
            item["username"] or "",
        )
    )

    return {
        "order_id": str(order.id),
        "public_number": order.public_number,
        "city_code": city.code,
        "drivers_count": len(drivers),
        "drivers": drivers,
    }


@router.post("/orders/{order_id}/assign")
def assign_order_to_driver(
    order_id: UUID,
    payload: AssignDriverRequest,
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    profile = get_dispatcher_profile(
        db,
        dispatcher,
    )

    order = db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .with_for_update()
    )

    if order is None:
        raise HTTPException(
            404,
            "Заказ не найден",
        )

    ensure_order_access(profile, order)

    city = validate_order_for_assignment(
        db,
        order,
    )

    driver_profile = db.get(
        DriverProfile,
        payload.driver_user_id,
    )

    if (
        driver_profile is None
        or not driver_profile.is_active
        or not driver_profile.is_online
    ):
        raise HTTPException(
            409,
            "Водитель неактивен или не находится на линии",
        )

    driver_user = db.get(
        User,
        payload.driver_user_id,
    )

    if driver_user is None or not driver_user.is_active:
        raise HTTPException(
            409,
            "Учётная запись водителя недоступна",
        )

    if driver_profile.city_id != order.city_id:
        raise HTTPException(
            409,
            "Водитель относится к другому городу",
        )

    branch_allowed = (
        driver_profile.branch_id == order.branch_id
        or driver_profile.branch_id is None
    )

    if not branch_allowed:
        raise HTTPException(
            409,
            "Водитель относится к другому таксопарку",
        )

    vehicle = db.get(
        Vehicle,
        payload.vehicle_id,
    )

    if (
        vehicle is None
        or not vehicle.is_active
        or vehicle.driver_user_id != payload.driver_user_id
        or vehicle.city_id != order.city_id
    ):
        raise HTTPException(
            409,
            "Автомобиль недоступен или не принадлежит водителю",
        )

    busy_driver_ids = get_busy_driver_ids(db)

    if payload.driver_user_id in busy_driver_ids:
        raise HTTPException(
            409,
            "У водителя уже есть активный заказ",
        )

    return save_driver_assignment(
        db=db,
        order=order,
        driver_profile=driver_profile,
        vehicle=vehicle,
        dispatcher=dispatcher,
        city=city,
    )


@router.post("/orders/{order_id}/auto-assign")
def auto_assign_order(
    order_id: UUID,
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    profile = get_dispatcher_profile(
        db,
        dispatcher,
    )

    order = db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .with_for_update()
    )

    if order is None:
        raise HTTPException(
            404,
            "Заказ не найден",
        )

    ensure_order_access(profile, order)

    validate_order_for_assignment(
        db,
        order,
    )

    return create_next_driver_offer(
        db=db,
        order=order,
    )


@router.post("/orders/{order_id}/accept")
def accept_order_and_assign_driver(
    order_id: UUID,
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    profile = get_dispatcher_profile(
        db,
        dispatcher,
    )

    order = db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .with_for_update()
    )

    if order is None:
        raise HTTPException(
            404,
            "Заказ не найден",
        )

    ensure_order_access(profile, order)

    if order.status != "new":
        raise HTTPException(
            409,
            "Принять можно только новый заказ",
        )

    old_status = order.status
    order.status = "accepted"
    order.updated_at = datetime.now(timezone.utc)

    db.add(
        OrderStatusHistory(
            order_id=order.id,
            old_status=old_status,
            new_status="accepted",
            changed_by_user_id=dispatcher.id,
        )
    )

    try:
        db.commit()
        db.refresh(order)
    except Exception:
        db.rollback()
        raise

    try:
        assignment_result = auto_assign_order(
            order_id=order_id,
            dispatcher=dispatcher,
            db=db,
        )

        assignment_result["accepted"] = True
        assignment_result["message"] = (
            "Заказ принят. Предложение отправлено водителю."
        )

        return assignment_result

    except HTTPException as exc:
        if (
            exc.status_code == 409
            and exc.detail == NO_AVAILABLE_DRIVERS_MESSAGE
        ):
            return {
                "success": True,
                "accepted": True,
                "offered": False,
                "assigned": False,
                "message": (
                    "Заказ принят. Свободных водителей нет, "
                    "ожидается вмешательство диспетчера."
                ),
                "order_id": str(order.id),
                "public_number": order.public_number,
                "status": "accepted",
                "driver_user_id": None,
                "vehicle_id": None,
            }

        raise
