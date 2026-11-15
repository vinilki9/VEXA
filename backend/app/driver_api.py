
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Branch,
    City,
    DriverLocation,
    DriverProfile,
    User,
    Vehicle,
)
from app.security import (
    create_driver_access_token,
    get_current_driver,
    verify_password,
)

from app.dispatch_driver_api import router as dispatch_driver_router


router = APIRouter(
    tags=["Driver"],
)


class DriverLoginRequest(BaseModel):
    login: str = Field(
        min_length=3,
        max_length=80,
    )

    password: str = Field(
        min_length=1,
        max_length=128,
    )


class DriverOnlineRequest(BaseModel):
    is_online: bool


class DriverLocationRequest(BaseModel):
    latitude: float = Field(
        ge=-90,
        le=90,
    )

    longitude: float = Field(
        ge=-180,
        le=180,
    )

    accuracy_meters: float | None = Field(
        default=None,
        ge=0,
    )


def get_driver_profile(
    db: Session,
    driver: User,
) -> DriverProfile:
    profile = db.get(
        DriverProfile,
        driver.id,
    )

    if profile is None or not profile.is_active:
        raise HTTPException(
            403,
            "Профиль водителя недоступен",
        )

    city = db.get(
        City,
        profile.city_id,
    )

    if city is None or not city.is_active:
        raise HTTPException(
            403,
            "Город водителя неактивен",
        )

    if profile.branch_id is not None:
        branch = db.get(
            Branch,
            profile.branch_id,
        )

        if (
            branch is None
            or not branch.is_active
            or branch.city_id != profile.city_id
        ):
            raise HTTPException(
                403,
                "Филиал водителя недоступен",
            )

    return profile


def driver_profile_response(
    db: Session,
    driver: User,
    profile: DriverProfile,
) -> dict:
    city = db.get(
        City,
        profile.city_id,
    )

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
        raise HTTPException(
            401,
            "Неверный логин или пароль",
        )

    profile = db.get(
        DriverProfile,
        driver.id,
    )

    if profile is None or not profile.is_active:
        raise HTTPException(
            401,
            "Учётная запись водителя недоступна",
        )

    try:
        get_driver_profile(
            db,
            driver,
        )
    except HTTPException:
        raise HTTPException(
            403,
            "Город или филиал водителя недоступен",
        )

    return {
        "access_token": create_driver_access_token(
            driver.id
        ),
        "token_type": "bearer",
    }


@router.get("/api/v1/driver/me")
def driver_me(
    driver: User = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    profile = get_driver_profile(
        db,
        driver,
    )

    return driver_profile_response(
        db,
        driver,
        profile,
    )


@router.post("/api/v1/driver/online")
def set_driver_online(
    payload: DriverOnlineRequest,
    driver: User = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    profile = get_driver_profile(
        db,
        driver,
    )

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
    get_driver_profile(
        db,
        driver,
    )

    now = datetime.now(timezone.utc)

    location = db.get(
        DriverLocation,
        driver.id,
    )

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


# Подключаем диспетчерские маршруты без изменения их URL.
router.include_router(dispatch_driver_router)
