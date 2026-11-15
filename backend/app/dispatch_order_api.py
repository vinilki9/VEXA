
from datetime import datetime, timezone
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

    if profile.role == "dispatcher":
        if order.branch_id != profile.branch_id:
            raise HTTPException(
                404,
                "Заказ не найден",
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

    if order.status != "accepted":
        raise HTTPException(
            409,
            "Сначала необходимо принять заказ диспетчером",
        )

    if order.driver_user_id is not None:
        raise HTTPException(
            409,
            "К заказу уже назначен водитель",
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

    return {
        "success": True,
        "message": "Водитель назначен на заказ",
        "order_id": str(order.id),
        "public_number": order.public_number,
        "status": order.status,
        "driver_user_id": str(order.driver_user_id),
        "vehicle_id": str(order.vehicle_id),
        "city_code": city.code,
    }
