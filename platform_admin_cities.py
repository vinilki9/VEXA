
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import City
from app.organization_access_models import AuditLog
from app.platform_admin_auth import get_current_platform_admin


router = APIRouter(
    prefix="/api/v1/platform-admin/cities",
    tags=["Platform Admin Cities"],
    dependencies=[Depends(get_current_platform_admin)],
)


class CityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=80)


class CityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    code: str | None = Field(default=None, min_length=2, max_length=80)
    is_active: bool | None = None


def normalize_city_code(value: str) -> str:
    code = value.strip().lower()

    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Код города должен содержать латинские буквы, цифры и дефисы",
        )

    return code


def get_city_or_404(db: Session, city_id: UUID) -> City:
    city = db.get(City, city_id)

    if city is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Город не найден",
        )

    return city


def write_city_audit(
    db: Session,
    admin_id: UUID,
    action: str,
    city: City,
    before_data: dict | None = None,
    after_data: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=admin_id,
            action=action,
            entity_type="city",
            entity_id=str(city.id),
            before_data=before_data,
            after_data=after_data,
        )
    )


def city_response(city: City) -> dict:
    return {
        "id": str(city.id),
        "name": city.name,
        "code": city.code,
        "is_active": city.is_active,
        "created_at": city.created_at,
    }


@router.get("")
def list_cities(
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    query = select(City).order_by(City.name.asc())

    if active_only:
        query = query.where(City.is_active.is_(True))

    cities = db.scalars(query).all()

    return {
        "items": [city_response(city) for city in cities],
        "total": len(cities),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_city(
    payload: CityCreate,
    admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()

    if len(name) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Название города должно содержать минимум 2 символа",
        )

    code = normalize_city_code(payload.code)

    city = City(
        name=name,
        code=code,
        is_active=True,
    )

    db.add(city)

    try:
        db.flush()

        write_city_audit(
            db=db,
            admin_id=admin.id,
            action="city.created",
            city=city,
            after_data={
                "name": city.name,
                "code": city.code,
                "is_active": city.is_active,
            },
        )

        db.commit()
        db.refresh(city)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Город с таким кодом уже существует",
        )

    return city_response(city)


@router.patch("/{city_id}")
def update_city(
    city_id: UUID,
    payload: CityUpdate,
    admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    city = get_city_or_404(db, city_id)

    supplied_fields = payload.model_fields_set

    if not supplied_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не указаны поля для изменения",
        )

    before_data = {
        "name": city.name,
        "code": city.code,
        "is_active": city.is_active,
    }

    if "name" in supplied_fields:
        if payload.name is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Название города не может быть пустым",
            )

        name = payload.name.strip()

        if len(name) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Название города должно содержать минимум 2 символа",
            )

        city.name = name

    if "code" in supplied_fields:
        if payload.code is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Код города не может быть пустым",
            )

        city.code = normalize_city_code(payload.code)

    if "is_active" in supplied_fields:
        if payload.is_active is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Необходимо указать состояние города",
            )

        city.is_active = payload.is_active

    after_data = {
        "name": city.name,
        "code": city.code,
        "is_active": city.is_active,
    }

    if before_data == after_data:
        return {
            **city_response(city),
            "changed": False,
        }

    try:
        write_city_audit(
            db=db,
            admin_id=admin.id,
            action="city.updated",
            city=city,
            before_data=before_data,
            after_data=after_data,
        )

        db.commit()
        db.refresh(city)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Город с таким кодом уже существует",
        )

    return {
        **city_response(city),
        "changed": True,
    }
