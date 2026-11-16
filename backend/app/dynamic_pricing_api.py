
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dispatch_order_api import get_dispatcher_profile
from app.models import (
    Branch,
    City,
    DynamicPricingChangeHistory,
    DynamicPricingSettings,
    User,
)
from app.security import get_current_dispatcher


router = APIRouter(
    prefix="/api/v1/dispatch/dynamic-pricing",
    tags=["Dispatcher Dynamic Pricing"],
)


DEFAULT_VALUES = {
    "max_multiplier": Decimal("2.50"),
    "driver_radius_km": Decimal("4.00"),
    "driver_distance_start_multiplier": Decimal("1.50"),
    "driver_distance_threshold_km": Decimal("20.00"),
    "driver_distance_threshold_multiplier": Decimal("2.00"),
    "driver_distance_step_km": Decimal("3.00"),
    "driver_distance_step_multiplier": Decimal("0.20"),
    "weather_enabled": False,
    "weather_addition": Decimal("0.00"),
    "traffic_enabled": False,
    "traffic_addition": Decimal("0.00"),
    "demand_enabled": False,
    "demand_addition": Decimal("0.00"),
    "other_enabled": False,
    "other_addition": Decimal("0.00"),
    "is_active": True,
}


DECIMAL_FIELDS = {
    "max_multiplier",
    "driver_radius_km",
    "driver_distance_start_multiplier",
    "driver_distance_threshold_km",
    "driver_distance_threshold_multiplier",
    "driver_distance_step_km",
    "driver_distance_step_multiplier",
    "weather_addition",
    "traffic_addition",
    "demand_addition",
    "other_addition",
}

SETTING_FIELDS = set(DEFAULT_VALUES)


class DynamicPricingUpdate(BaseModel):
    max_multiplier: Decimal | None = Field(default=None, ge=1)
    driver_radius_km: Decimal | None = Field(default=None, ge=0)
    driver_distance_start_multiplier: Decimal | None = Field(
        default=None,
        ge=1,
    )
    driver_distance_threshold_km: Decimal | None = Field(
        default=None,
        gt=0,
    )
    driver_distance_threshold_multiplier: Decimal | None = Field(
        default=None,
        ge=1,
    )
    driver_distance_step_km: Decimal | None = Field(
        default=None,
        gt=0,
    )
    driver_distance_step_multiplier: Decimal | None = Field(
        default=None,
        ge=0,
    )

    weather_enabled: bool | None = None
    weather_addition: Decimal | None = Field(default=None, ge=0)

    traffic_enabled: bool | None = None
    traffic_addition: Decimal | None = Field(default=None, ge=0)

    demand_enabled: bool | None = None
    demand_addition: Decimal | None = Field(default=None, ge=0)

    other_enabled: bool | None = None
    other_addition: Decimal | None = Field(default=None, ge=0)

    is_active: bool | None = None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _decimal_to_string(value) -> str:
    return str(Decimal(value))


def _settings_snapshot(settings: DynamicPricingSettings) -> dict:
    result = {
        "id": str(settings.id),
        "city_id": str(settings.city_id),
        "branch_id": (
            str(settings.branch_id)
            if settings.branch_id is not None
            else None
        ),
        "created_at": settings.created_at.isoformat(),
        "updated_at": settings.updated_at.isoformat(),
    }

    for field in SETTING_FIELDS:
        value = getattr(settings, field)

        if field in DECIMAL_FIELDS:
            result[field] = _decimal_to_string(value)
        else:
            result[field] = value

    return result


def _default_settings(
    city: City,
    branch_id: UUID | None,
) -> dict:
    result = {
        "id": None,
        "city_id": str(city.id),
        "branch_id": (
            str(branch_id)
            if branch_id is not None
            else None
        ),
        "scope": "defaults",
        "inherited": True,
    }

    for field, value in DEFAULT_VALUES.items():
        result[field] = (
            _decimal_to_string(value)
            if field in DECIMAL_FIELDS
            else value
        )

    return result


def _validate_settings_values(values: dict) -> None:
    radius = Decimal(values["driver_radius_km"])
    threshold_km = Decimal(
        values["driver_distance_threshold_km"]
    )
    start_multiplier = Decimal(
        values["driver_distance_start_multiplier"]
    )
    threshold_multiplier = Decimal(
        values["driver_distance_threshold_multiplier"]
    )

    if threshold_km <= radius:
        raise HTTPException(
            422,
            "Порог расстояния должен быть больше радиуса первого круга",
        )

    if threshold_multiplier < start_multiplier:
        raise HTTPException(
            422,
            "Коэффициент на пороге расстояния не может быть меньше начального",
        )


def _resolve_dispatcher_scope(
    db: Session,
    dispatcher: User,
    city_id: UUID | None,
    branch_id: UUID | None,
):
    profile = get_dispatcher_profile(db, dispatcher)

    if profile.role == "dispatcher":
        own_branch = db.get(Branch, profile.branch_id)

        if own_branch is None or not own_branch.is_active:
            raise HTTPException(
                403,
                "Филиал диспетчера недоступен",
            )

        if city_id is not None and city_id != own_branch.city_id:
            raise HTTPException(
                404,
                "Настройки не найдены",
            )

        if branch_id is not None and branch_id != own_branch.id:
            raise HTTPException(
                404,
                "Настройки не найдены",
            )

        resolved_city_id = own_branch.city_id
        resolved_branch_id = own_branch.id

    elif profile.role == "chief_dispatcher":
        if city_id is None:
            raise HTTPException(
                422,
                "Для главного диспетчера необходимо указать city_id",
            )

        resolved_city_id = city_id
        resolved_branch_id = branch_id

    else:
        raise HTTPException(
            403,
            "Недостаточно прав",
        )

    city = db.get(City, resolved_city_id)

    if city is None or not city.is_active:
        raise HTTPException(
            404,
            "Город не найден или отключён",
        )

    branch = None

    if resolved_branch_id is not None:
        branch = db.get(Branch, resolved_branch_id)

        if (
            branch is None
            or not branch.is_active
            or branch.city_id != city.id
        ):
            raise HTTPException(
                404,
                "Филиал не найден в указанном городе",
            )

    return profile, city, branch


def _find_settings(
    db: Session,
    city_id: UUID,
    branch_id: UUID | None,
    lock: bool = False,
):
    query = select(DynamicPricingSettings).where(
        DynamicPricingSettings.city_id == city_id,
        DynamicPricingSettings.branch_id == branch_id,
    )

    if lock:
        query = query.with_for_update()

    records = db.scalars(query.limit(2)).all()

    if len(records) > 1:
        raise HTTPException(
            409,
            "Обнаружены дубли настроек динамического коэффициента. Требуется устранить дубли перед изменением.",
        )

    return records[0] if records else None


def _get_effective_settings(
    db: Session,
    city: City,
    branch: Branch | None,
):
    if branch is not None:
        branch_settings = _find_settings(
            db,
            city.id,
            branch.id,
        )

        if branch_settings is not None:
            result = _settings_snapshot(branch_settings)
            result["scope"] = "branch"
            result["inherited"] = False
            return result

    city_settings = _find_settings(
        db,
        city.id,
        None,
    )

    if city_settings is not None:
        result = _settings_snapshot(city_settings)
        result["scope"] = "city"
        result["inherited"] = branch is not None
        return result

    return _default_settings(
        city,
        branch.id if branch is not None else None,
    )


@router.get("")
def get_dynamic_pricing_settings(
    city_id: UUID | None = None,
    branch_id: UUID | None = None,
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    _, city, branch = _resolve_dispatcher_scope(
        db,
        dispatcher,
        city_id,
        branch_id,
    )

    return _get_effective_settings(
        db,
        city,
        branch,
    )


@router.put("")
def update_dynamic_pricing_settings(
    payload: DynamicPricingUpdate,
    city_id: UUID,
    branch_id: UUID | None = None,
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    profile = get_dispatcher_profile(db, dispatcher)

    if profile.role != "chief_dispatcher":
        raise HTTPException(
            403,
            "Изменять настройки динамического коэффициента может только главный диспетчер",
        )

    _, city, branch = _resolve_dispatcher_scope(
        db,
        dispatcher,
        city_id,
        branch_id,
    )

    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            422,
            "Не переданы параметры для изменения",
        )

    if any(value is None for value in changes.values()):
        raise HTTPException(
            422,
            "Параметры настроек не могут иметь значение null",
        )

    # Блокируем строку города, чтобы параллельные запросы
    # не создали несколько city-level записей с branch_id = NULL.
    locked_city = db.scalar(
        select(City)
        .where(City.id == city.id)
        .with_for_update()
    )

    if locked_city is None or not locked_city.is_active:
        raise HTTPException(
            404,
            "Город недоступен",
        )

    settings = _find_settings(
        db,
        city.id,
        branch.id if branch is not None else None,
        lock=True,
    )

    if settings is None:
        current_values = dict(DEFAULT_VALUES)
        current_values.update(changes)

        _validate_settings_values(current_values)

        now = _now_utc()

        settings = DynamicPricingSettings(
            city_id=city.id,
            branch_id=branch.id if branch is not None else None,
            **current_values,
            created_at=now,
            updated_at=now,
        )

        db.add(settings)
        action = "created"
        old_values = None

    else:
        old_values = _settings_snapshot(settings)

        current_values = {
            field: getattr(settings, field)
            for field in SETTING_FIELDS
        }
        current_values.update(changes)

        _validate_settings_values(current_values)

        for field, value in changes.items():
            setattr(settings, field, value)

        settings.updated_at = _now_utc()
        action = "updated"

    db.flush()

    new_values = _settings_snapshot(settings)

    db.add(
        DynamicPricingChangeHistory(
            settings_id=settings.id,
            city_id=city.id,
            branch_id=branch.id if branch is not None else None,
            changed_by_user_id=dispatcher.id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            changed_at=_now_utc(),
        )
    )

    try:
        db.commit()
        db.refresh(settings)
    except Exception:
        db.rollback()
        raise

    result = _settings_snapshot(settings)
    result["scope"] = "branch" if branch is not None else "city"
    result["inherited"] = False

    return {
        "success": True,
        "message": "Настройки динамического коэффициента сохранены",
        "settings": result,
    }


@router.get("/history")
def get_dynamic_pricing_history(
    city_id: UUID | None = None,
    branch_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    dispatcher: User = Depends(get_current_dispatcher),
    db: Session = Depends(get_db),
):
    profile, city, branch = _resolve_dispatcher_scope(
        db,
        dispatcher,
        city_id,
        branch_id,
    )

    query = select(
        DynamicPricingChangeHistory
    ).where(
        DynamicPricingChangeHistory.city_id == city.id,
    )

    if profile.role == "dispatcher":
        # Обычный диспетчер видит историю своего филиала
        # и историю городских настроек, от которых он наследует значения.
        query = query.where(
            or_(
                DynamicPricingChangeHistory.branch_id.is_(None),
                DynamicPricingChangeHistory.branch_id == branch.id,
            )
        )

    elif branch is not None:
        # При просмотре конкретного филиала показываем
        # его историю и историю городских значений по умолчанию.
        query = query.where(
            or_(
                DynamicPricingChangeHistory.branch_id.is_(None),
                DynamicPricingChangeHistory.branch_id == branch.id,
            )
        )

    records = db.scalars(
        query
        .order_by(
            DynamicPricingChangeHistory.changed_at.desc()
        )
        .limit(limit)
    ).all()

    return {
        "city_id": str(city.id),
        "branch_id": (
            str(branch.id)
            if branch is not None
            else None
        ),
        "items": [
            {
                "id": str(item.id),
                "settings_id": str(item.settings_id),
                "city_id": str(item.city_id),
                "branch_id": (
                    str(item.branch_id)
                    if item.branch_id is not None
                    else None
                ),
                "changed_by_user_id": str(
                    item.changed_by_user_id
                ),
                "action": item.action,
                "old_values": item.old_values,
                "new_values": item.new_values,
                "changed_at": item.changed_at.isoformat(),
            }
            for item in records
        ],
    }
