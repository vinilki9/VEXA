
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Branch,
    City,
    DispatcherProfile,
    DriverLocation,
    DriverProfile,
    User,
)
from app.security import get_current_dispatcher


router = APIRouter(
    prefix="/api/v1/dispatch",
    tags=["Dispatcher Drivers"],
)


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


@router.get("/drivers/locations")
def list_driver_locations(
    city_code: str = "obolensk",
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    profile = get_dispatcher_profile(
        db,
        dispatcher,
    )

    branch = None

    if profile.role == "dispatcher":
        branch = db.get(
            Branch,
            profile.branch_id,
        )

        if branch is None or not branch.is_active:
            raise HTTPException(
                403,
                "Филиал диспетчера недоступен",
            )

        city = db.get(
            City,
            branch.city_id,
        )

        if city is None or not city.is_active:
            raise HTTPException(
                403,
                "Город филиала недоступен",
            )

    else:
        city = db.scalar(
            select(City).where(
                City.code == city_code,
                City.is_active.is_(True),
            )
        )

        if city is None:
            raise HTTPException(
                404,
                "Город не найден или неактивен",
            )

    query = (
        select(
            DriverProfile,
            User,
            DriverLocation,
            City,
            Branch,
        )
        .join(
            User,
            User.id == DriverProfile.user_id,
        )
        .join(
            City,
            City.id == DriverProfile.city_id,
        )
        .outerjoin(
            DriverLocation,
            DriverLocation.driver_user_id
            == DriverProfile.user_id,
        )
        .outerjoin(
            Branch,
            Branch.id == DriverProfile.branch_id,
        )
        .where(
            DriverProfile.city_id == city.id,
            DriverProfile.is_active.is_(True),
            User.is_active.is_(True),
            City.is_active.is_(True),
        )
    )

    if profile.role == "dispatcher":
        query = query.where(
            DriverProfile.branch_id == profile.branch_id,
        )

    rows = db.execute(
        query.order_by(
            DriverProfile.is_online.desc(),
            User.username,
        )
    ).all()

    drivers = []

    for driver_profile, user, location, driver_city, driver_branch in rows:
        drivers.append(
            {
                "user_id": str(user.id),
                "username": user.username,
                "phone": user.phone,
                "city": {
                    "id": str(driver_city.id),
                    "code": driver_city.code,
                    "name": driver_city.name,
                },
                "branch": (
                    {
                        "id": str(driver_branch.id),
                        "name": driver_branch.name,
                    }
                    if driver_branch is not None
                    else None
                ),
                "is_online": driver_profile.is_online,
                "rating": str(driver_profile.rating),
                "location": (
                    {
                        "latitude": location.latitude,
                        "longitude": location.longitude,
                        "accuracy_meters": (
                            location.accuracy_meters
                        ),
                        "recorded_at": location.recorded_at,
                        "updated_at": location.updated_at,
                    }
                    if location is not None
                    else None
                ),
            }
        )

    return {
        "city_code": city.code,
        "drivers_count": len(drivers),
        "drivers": drivers,
    }
