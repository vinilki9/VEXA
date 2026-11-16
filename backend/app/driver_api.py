
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Branch,
    DispatcherProfile,
    City,
    DriverFinanceTransaction,
    DriverLocation,
    DriverProfile,
    Order,
    OrderStatusHistory,
    User,
    Vehicle,
)
from app.security import (
    create_driver_access_token,
    get_current_dispatcher,
    get_current_driver,
    verify_password,
)

from app.dispatch_driver_api import router as dispatch_driver_router
from app.dispatch_order_api import router as dispatch_order_router


router = APIRouter(tags=["Driver"])


DRIVER_ORDER_STATUS_TRANSITIONS = {
    "assigned": "arrived",
    "arrived": "in_progress",
    "in_progress": "completed",
}


# Комиссия сервиса в зависимости от рейтинга водителя.
def get_driver_commission_rate(rating: Decimal) -> Decimal:
    if rating < Decimal("4.20"):
        return Decimal("10.00")
    if rating < Decimal("4.50"):
        return Decimal("9.00")
    if rating < Decimal("4.70"):
        return Decimal("8.00")
    if rating < Decimal("4.90"):
        return Decimal("6.00")
    return Decimal("4.00")


def calculate_commission(fare_kopecks: int, rate: Decimal) -> int:
    amount = (
        Decimal(fare_kopecks)
        * rate
        / Decimal("100")
    )
    return int(
        amount.quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


class DriverLoginRequest(BaseModel):
    login: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class DriverOnlineRequest(BaseModel):
    is_online: bool


class DriverLocationRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, ge=0)


class DriverOrderStatusRequest(BaseModel):
    status: str = Field(min_length=1, max_length=30)


class DriverDebtRepaymentRequest(BaseModel):
    amount_kopecks: int = Field(gt=0, le=2147483647)
    payment_method: Literal["cash", "driver_transfer"]


def get_driver_profile(
    db: Session,
    driver: User,
) -> DriverProfile:
    profile = db.get(DriverProfile, driver.id)

    if profile is None or not profile.is_active:
        raise HTTPException(403, "Профиль водителя недоступен")

    city = db.get(City, profile.city_id)

    if city is None or not city.is_active:
        raise HTTPException(403, "Город водителя неактивен")

    if profile.branch_id is not None:
        branch = db.get(Branch, profile.branch_id)

        if (
            branch is None
            or not branch.is_active
            or branch.city_id != profile.city_id
        ):
            raise HTTPException(403, "Филиал водителя недоступен")

    return profile


def driver_profile_response(
    db: Session,
    driver: User,
    profile: DriverProfile,
) -> dict:
    city = db.get(City, profile.city_id)

    branch = (
        db.get(Branch, profile.branch_id)
        if profile.branch_id is not None
        else None
    )

    vehicles = db.scalars(
        select(Vehicle)
        .where(
            Vehicle.driver_user_id == driver.id,
            Vehicle.city_id == profile.city_id,
            Vehicle.is_active.is_(True),
        )
        .order_by(Vehicle.created_at.desc())
    ).all()

    return {
        "user_id": str(driver.id),
        "username": driver.username,
        "phone": driver.phone,
        "is_active": driver.is_active and profile.is_active,
        "is_online": profile.is_online,
        "rating": str(profile.rating),
        "city": {
            "id": str(city.id),
            "code": city.code,
            "name": city.name,
        },
        "branch": (
            {
                "id": str(branch.id),
                "name": branch.name,
            }
            if branch is not None
            else None
        ),
        "vehicles": [
            {
                "id": str(vehicle.id),
                "make": vehicle.make,
                "model": vehicle.model,
                "color": vehicle.color,
                "license_plate": vehicle.license_plate,
            }
            for vehicle in vehicles
        ],
    }


def driver_order_response(
    order: Order,
    vehicle: Vehicle | None,
) -> dict:
    return {
        "id": str(order.id),
        "public_number": order.public_number,
        "city_id": str(order.city_id),
        "branch_id": (
            str(order.branch_id)
            if order.branch_id is not None
            else None
        ),
        "status": order.status,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "anonymous": order.anonymous,
        "pickup": {
            "address": order.pickup_address,
            "latitude": order.pickup_latitude,
            "longitude": order.pickup_longitude,
        },
        "destination": {
            "address": order.destination_address,
            "latitude": order.destination_latitude,
            "longitude": order.destination_longitude,
        },
        "route": {
            "distance_meters": order.route_distance_meters,
            "duration_seconds": order.route_duration_seconds,
        },
        "payment_method": order.payment_method,
        "price_rub": order.price_rub,
        "price_kopecks": order.price_kopecks,
        "cargo": (
            {
                "vehicle": order.cargo_vehicle,
                "description": order.cargo_description,
                "loaders": order.cargo_loaders,
                "vehicle_surcharge_kopecks": (
                    order.cargo_vehicle_surcharge_kopecks
                ),
                "loaders_surcharge_kopecks": (
                    order.cargo_loaders_surcharge_kopecks
                ),
            }
            if order.cargo_vehicle is not None
            else None
        ),
        "vehicle": (
            {
                "id": str(vehicle.id),
                "make": vehicle.make,
                "model": vehicle.model,
                "color": vehicle.color,
                "license_plate": vehicle.license_plate,
            }
            if vehicle is not None
            else None
        ),
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


def create_completed_trip_finance(
    db: Session,
    order: Order,
    driver: User,
    profile: DriverProfile,
) -> None:
    # Блокировка профиля синхронизирует начисление комиссии
    # и регистрацию погашения задолженности.
    locked_profile = db.scalar(
        select(DriverProfile)
        .where(DriverProfile.user_id == driver.id)
        .with_for_update()
    )

    if locked_profile is None or not locked_profile.is_active:
        raise HTTPException(409, "Профиль водителя недоступен")

    profile = locked_profile

    existing = db.scalar(
        select(DriverFinanceTransaction.id).where(
            DriverFinanceTransaction.order_id == order.id,
            DriverFinanceTransaction.transaction_type == "completed_trip",
        )
    )

    if existing is not None:
        return

    fare_kopecks = order.price_kopecks

    if fare_kopecks is None and order.price_rub is not None:
        fare_kopecks = order.price_rub * 100

    if fare_kopecks is None or fare_kopecks < 0:
        raise HTTPException(
            409,
            "Невозможно завершить поездку: стоимость заказа не указана",
        )

    rating = Decimal(str(profile.rating))
    commission_rate = get_driver_commission_rate(rating)
    commission_kopecks = calculate_commission(
        fare_kopecks,
        commission_rate,
    )

    driver_earning_kopecks = fare_kopecks - commission_kopecks

    if order.payment_method == "cash":
        debt_change_kopecks = commission_kopecks
    elif order.payment_method in (
        "driver_transfer",
        "card",
        "sbp",
    ):
        debt_change_kopecks = 0
    else:
        raise HTTPException(
            409,
            "Неизвестный способ оплаты заказа",
        )

    db.add(
        DriverFinanceTransaction(
            driver_user_id=driver.id,
            order_id=order.id,
            city_id=order.city_id,
            branch_id=order.branch_id,
            transaction_type="completed_trip",
            payment_method=order.payment_method,
            driver_rating=rating,
            fare_kopecks=fare_kopecks,
            commission_rate_percent=commission_rate,
            commission_kopecks=commission_kopecks,
            driver_earning_kopecks=driver_earning_kopecks,
            debt_change_kopecks=debt_change_kopecks,
            description=(
                f"Завершённая поездка №{order.public_number}"
            ),
        )
    )


def finance_transaction_response(
    transaction: DriverFinanceTransaction,
) -> dict:
    return {
        "id": str(transaction.id),
        "order_id": (
            str(transaction.order_id)
            if transaction.order_id is not None
            else None
        ),
        "transaction_type": transaction.transaction_type,
        "payment_method": transaction.payment_method,
        "driver_rating": (
            str(transaction.driver_rating)
            if transaction.driver_rating is not None
            else None
        ),
        "fare_kopecks": transaction.fare_kopecks,
        "commission_rate_percent": str(
            transaction.commission_rate_percent
        ),
        "commission_kopecks": transaction.commission_kopecks,
        "driver_earning_kopecks": (
            transaction.driver_earning_kopecks
        ),
        "debt_change_kopecks": transaction.debt_change_kopecks,
        "description": transaction.description,
        "created_at": transaction.created_at,
    }


@router.post("/api/v1/driver/auth/login")
def driver_login(
    payload: DriverLoginRequest,
    db: Session = Depends(get_db),
):
    login_value = payload.login.strip()

    driver = db.scalar(
        select(User).where(
            or_(
                User.username == login_value,
                User.phone == login_value,
            )
        )
    )

    if (
        driver is None
        or not driver.is_active
        or not driver.password_hash
        or not verify_password(
            payload.password,
            driver.password_hash,
        )
    ):
        raise HTTPException(401, "Неверный логин или пароль")

    profile = db.get(DriverProfile, driver.id)

    if profile is None or not profile.is_active:
        raise HTTPException(
            401,
            "Учётная запись водителя недоступна",
        )

    get_driver_profile(db, driver)

    return {
        "access_token": create_driver_access_token(driver.id),
        "token_type": "bearer",
    }


@router.get("/api/v1/driver/me")
def driver_me(
    driver: User = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    profile = get_driver_profile(db, driver)

    return driver_profile_response(db, driver, profile)


@router.get("/api/v1/driver/orders/active")
def driver_active_orders(
    driver: User = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    profile = get_driver_profile(db, driver)

    orders = db.scalars(
        select(Order)
        .where(
            Order.driver_user_id == driver.id,
            Order.city_id == profile.city_id,
            Order.status.in_(
                ["assigned", "arrived", "in_progress"]
            ),
        )
        .order_by(Order.created_at.asc())
    ).all()

    result = []

    for order in orders:
        vehicle = (
            db.get(Vehicle, order.vehicle_id)
            if order.vehicle_id is not None
            else None
        )

        result.append(driver_order_response(order, vehicle))

    return {
        "orders_count": len(result),
        "orders": result,
    }


@router.post("/api/v1/driver/orders/{order_id}/status")
def update_driver_order_status(
    order_id: str,
    payload: DriverOrderStatusRequest,
    driver: User = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    profile = get_driver_profile(db, driver)

    order = db.scalar(
        select(Order)
        .where(
            Order.id == order_id,
            Order.driver_user_id == driver.id,
            Order.city_id == profile.city_id,
        )
        .with_for_update()
    )

    if order is None:
        raise HTTPException(
            404,
            "Активный заказ водителя не найден",
        )

    expected_status = DRIVER_ORDER_STATUS_TRANSITIONS.get(
        order.status
    )

    if expected_status is None:
        raise HTTPException(
            409,
            "Для этого заказа изменение статуса водителем запрещено",
        )

    if payload.status != expected_status:
        raise HTTPException(
            409,
            (
                f"Недопустимый переход статуса: "
                f"{order.status} -> {payload.status}. "
                f"Следующий статус: {expected_status}"
            ),
        )

    old_status = order.status
    now = datetime.now(timezone.utc)

    order.status = payload.status
    order.updated_at = now

    db.add(
        OrderStatusHistory(
            order_id=order.id,
            old_status=old_status,
            new_status=payload.status,
            changed_by_user_id=driver.id,
        )
    )

    if payload.status == "completed":
        create_completed_trip_finance(
            db=db,
            order=order,
            driver=driver,
            profile=profile,
        )

    try:
        db.commit()
        db.refresh(order)
    except Exception:
        db.rollback()
        raise

    vehicle = (
        db.get(Vehicle, order.vehicle_id)
        if order.vehicle_id is not None
        else None
    )

    return {
        "success": True,
        "message": "Статус заказа обновлён",
        "order": driver_order_response(order, vehicle),
    }


@router.get("/api/v1/driver/finance")
def driver_finance_summary(
    driver: User = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    profile = get_driver_profile(db, driver)

    totals = db.execute(
        select(
            func.coalesce(
                func.sum(
                    DriverFinanceTransaction.fare_kopecks
                ),
                0,

            ),
            func.coalesce(
                func.sum(
                    DriverFinanceTransaction.commission_kopecks
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    DriverFinanceTransaction.driver_earning_kopecks
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    DriverFinanceTransaction.debt_change_kopecks
                ),
                0,
            ),
            func.count(DriverFinanceTransaction.id).filter(
                DriverFinanceTransaction.transaction_type == "completed_trip"
            ),
        ).where(
            DriverFinanceTransaction.driver_user_id == driver.id,
            DriverFinanceTransaction.city_id == profile.city_id,
        )
    ).one()

    return {
        "currency": "RUB",
        "fare_total_kopecks": int(totals[0]),
        "commission_total_kopecks": int(totals[1]),
        "earnings_total_kopecks": int(totals[2]),
        "cash_debt_kopecks": int(totals[3]),
        "completed_trips": int(totals[4]),
        "current_rating": str(profile.rating),
        "current_commission_rate_percent": str(
            get_driver_commission_rate(
                Decimal(str(profile.rating))
            )
        ),
    }

 


@router.post(
    "/api/v1/dispatch/drivers/{driver_user_id}/finance/repayments"
)
def register_driver_debt_repayment(
    driver_user_id: UUID,
    payload: DriverDebtRepaymentRequest,
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    dispatcher_profile = db.get(DispatcherProfile, dispatcher.id)

    if (
        dispatcher_profile is None
        or not dispatcher_profile.is_active
    ):
        raise HTTPException(403, "Доступ диспетчера запрещён")

    driver_profile = db.scalar(
        select(DriverProfile)
        .where(DriverProfile.user_id == driver_user_id)
        .with_for_update()
    )

    if driver_profile is None or not driver_profile.is_active:
        raise HTTPException(404, "Водитель не найден или неактивен")

    city = db.get(City, driver_profile.city_id)

    if city is None or not city.is_active:
        raise HTTPException(409, "Город водителя неактивен")

    if dispatcher_profile.role == "chief_dispatcher":
        pass
    elif dispatcher_profile.role == "dispatcher":
        if (
            dispatcher_profile.branch_id is None
            or dispatcher_profile.branch_id != driver_profile.branch_id
        ):
            raise HTTPException(
                403,
                "Нет доступа к финансовым операциям этого водителя",
            )

        branch = db.get(Branch, dispatcher_profile.branch_id)

        if (
            branch is None
            or not branch.is_active
            or branch.city_id != driver_profile.city_id
        ):
            raise HTTPException(403, "Филиал диспетчера недоступен")
    else:
        raise HTTPException(403, "Недостаточно прав для погашения долга")

    current_debt_kopecks = db.scalar(
        select(
            func.coalesce(
                func.sum(DriverFinanceTransaction.debt_change_kopecks),
                0,
            )
        ).where(
            DriverFinanceTransaction.driver_user_id == driver_user_id,
            DriverFinanceTransaction.city_id == driver_profile.city_id,
        )
    )
    current_debt_kopecks = int(current_debt_kopecks or 0)

    if current_debt_kopecks <= 0:
        raise HTTPException(409, "У водителя нет задолженности")

    if payload.amount_kopecks > current_debt_kopecks:
        raise HTTPException(
            409,
            "Сумма погашения превышает текущую задолженность",
        )

    repayment = DriverFinanceTransaction(
        driver_user_id=driver_user_id,
        order_id=None,
        city_id=driver_profile.city_id,
        branch_id=driver_profile.branch_id,
        transaction_type="debt_repayment",
        payment_method=payload.payment_method,
        driver_rating=driver_profile.rating,
        fare_kopecks=0,
        commission_rate_percent=Decimal("0.00"),
        commission_kopecks=0,
        driver_earning_kopecks=0,
        debt_change_kopecks=-payload.amount_kopecks,
        description=(
            "Погашение задолженности водителем: "
            f"{payload.amount_kopecks / 100:.2f} ₽"
        ),
    )
    db.add(repayment)

    try:
        db.commit()
        db.refresh(repayment)
    except Exception:
        db.rollback()
        raise

    remaining_debt_kopecks = current_debt_kopecks - payload.amount_kopecks

    return {
        "success": True,
        "message": "Погашение задолженности зарегистрировано",
        "repayment": finance_transaction_response(repayment),
        "paid_kopecks": payload.amount_kopecks,
        "remaining_debt_kopecks": remaining_debt_kopecks,
    }


@router.get("/api/v1/driver/finance/transactions")
def driver_finance_transactions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    driver: User = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    profile = get_driver_profile(db, driver)

    transactions = db.scalars(
        select(DriverFinanceTransaction)
        .where(
            DriverFinanceTransaction.driver_user_id == driver.id,
            DriverFinanceTransaction.city_id == profile.city_id,
        )
        .order_by(
            DriverFinanceTransaction.created_at.desc(),
            DriverFinanceTransaction.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()

    return {
        "items": [
            finance_transaction_response(item)
            for item in transactions
        ],
        "limit": limit,
        "offset": offset,
    }

 

@router.post("/api/v1/driver/online")
def set_driver_online(
    payload: DriverOnlineRequest,
    driver: User = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    profile = get_driver_profile(db, driver)

    profile.is_online = payload.is_online

    db.commit()
    db.refresh(profile)

    return {
        "success": True,
        "is_online": profile.is_online,
    }


@router.post("/api/v1/driver/location")
def update_driver_location(
    payload: DriverLocationRequest,
    driver: User = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    get_driver_profile(db, driver)

    now = datetime.now(timezone.utc)

    location = db.get(DriverLocation, driver.id)

    if location is None:
        location = DriverLocation(
            driver_user_id=driver.id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy_meters=payload.accuracy_meters,
            recorded_at=now,
            updated_at=now,
        )
        db.add(location)
    else:
        location.latitude = payload.latitude
        location.longitude = payload.longitude
        location.accuracy_meters = payload.accuracy_meters
        location.recorded_at = now
        location.updated_at = now

    db.commit()
    db.refresh(location)

    return {
        "success": True,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "accuracy_meters": location.accuracy_meters,
        "recorded_at": location.recorded_at,
    }


# Подключаем диспетчерские маршруты GPS водителей.
router.include_router(dispatch_driver_router)

# Подключаем ручное и автоматическое назначение водителей.
router.include_router(dispatch_order_router)
