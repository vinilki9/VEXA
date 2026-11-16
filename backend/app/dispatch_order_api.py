
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
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
                "Диспетчер не привязан к филиалу",
            )

        branch = db.get(
            Branch,
            profile.branch_id,
        )

        if branch is None or not branch.is_active:
            raise HTTPException(
                403,
                "Филиал диспетчера недоступен",
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
            DriverProfile.branch_id == order.branch_id,
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

    if driver_profile.branch_id != order.branch_id:
        raise HTTPException(
            409,
            "Водитель относится к другому филиалу",
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

    city = validate_order_for_assignment(
        db,
        order,
    )

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

    driver_profiles = db.scalars(
        select(DriverProfile).where(
            DriverProfile.is_active.is_(True),
            DriverProfile.is_online.is_(True),
            DriverProfile.city_id == order.city_id,
            DriverProfile.branch_id == order.branch_id,
        )
    ).all()

    candidates = []

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

    if not candidates:
        raise HTTPException(
            409,
            NO_AVAILABLE_DRIVERS_MESSAGE,
        )

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        )
    )

    distance, _, _, selected_driver, selected_vehicle = (
        candidates[0]
    )

    return save_driver_assignment(
        db=db,
        order=order,
        driver_profile=selected_driver,
        vehicle=selected_vehicle,
        dispatcher=dispatcher,
        city=city,
        distance_meters=distance,
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
            "Заказ принят, водитель назначен автоматически"
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
                "assigned": False,
                "message": (
                    "Заказ принят. Свободных водителей нет, "
                    "назначьте водителя вручную."
                ),
                "order_id": str(order.id),
                "public_number": order.public_number,
                "status": "accepted",
                "driver_user_id": None,
                "vehicle_id": None,
            }

        raise
