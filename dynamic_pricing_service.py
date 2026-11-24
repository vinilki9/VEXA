
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from math import asin, cos, radians, sin, sqrt

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.dynamic_pricing import calculate_dynamic_multiplier
from app.models import (
    Branch,
    City,
    DriverLocation,
    DriverProfile,
    DynamicPricingSettings,
    Order,
    User,
    Vehicle,
)


GPS_MAX_AGE_MINUTES = 10
EARTH_RADIUS_KM = 6371.0088

DEFAULT_SETTINGS = {
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


def _haversine_distance_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> Decimal:
    lat_a = radians(latitude_a)
    lat_b = radians(latitude_b)

    delta_lat = radians(latitude_b - latitude_a)
    delta_lon = radians(longitude_b - longitude_a)

    value = (
        sin(delta_lat / 2) ** 2
        + cos(lat_a)
        * cos(lat_b)
        * sin(delta_lon / 2) ** 2
    )

    value = min(1.0, max(0.0, value))

    distance = (
        2
        * EARTH_RADIUS_KM
        * asin(sqrt(value))
    )

    return Decimal(str(distance))


def _get_effective_settings(
    db: Session,
    city: City,
    branch: Branch | None,
):
    if branch is not None:
        branch_settings = db.scalar(
            select(DynamicPricingSettings).where(
                DynamicPricingSettings.city_id == city.id,
                DynamicPricingSettings.branch_id == branch.id,
            ).limit(1)
        )

        if branch_settings is not None:
            return branch_settings, "branch"

    city_settings = db.scalar(
        select(DynamicPricingSettings).where(
            DynamicPricingSettings.city_id == city.id,
            DynamicPricingSettings.branch_id.is_(None),
        ).limit(1)
    )

    if city_settings is not None:
        return city_settings, "city"

    return None, "defaults"


def _settings_values(settings_row) -> dict:
    values = dict(DEFAULT_SETTINGS)

    if settings_row is not None:
        for field in DEFAULT_SETTINGS:
            values[field] = getattr(
                settings_row,
                field,
            )

    return values


def _find_nearest_available_driver_distance(
    db: Session,
    *,
    city: City,
    branch: Branch | None,
    pickup_latitude: float,
    pickup_longitude: float,
) -> Decimal | None:
    now = datetime.now(timezone.utc)
    gps_cutoff = now - timedelta(
        minutes=GPS_MAX_AGE_MINUTES
    )

    # Водитель не должен иметь активный заказ.
    active_order_exists = exists(
        select(Order.id).where(
            Order.driver_user_id == DriverProfile.user_id,
            Order.status.in_(
                (
                    "accepted",
                    "assigned",
                    "arrived",
                    "in_progress",
                )
            ),
        )
    )

    # У водителя должен быть активный автомобиль.
    active_vehicle_exists = exists(
        select(Vehicle.id).where(
            Vehicle.driver_user_id == DriverProfile.user_id,
            Vehicle.city_id == city.id,
            Vehicle.is_active.is_(True),
        )
    )

    query = (
        select(
            DriverLocation.latitude,
            DriverLocation.longitude,
        )
        .join(
            DriverProfile,
            DriverProfile.user_id
            == DriverLocation.driver_user_id,
        )
        .join(
            User,
            User.id == DriverProfile.user_id,
        )
        .where(
            DriverProfile.city_id == city.id,
            DriverProfile.is_active.is_(True),
            DriverProfile.is_online.is_(True),
            User.is_active.is_(True),
            DriverLocation.recorded_at >= gps_cutoff,
            active_vehicle_exists,
            ~active_order_exists,
        )
    )

    if branch is not None:
        query = query.where(
            or_(
                DriverProfile.branch_id == branch.id,
                DriverProfile.branch_id.is_(None),
            )
        )

    locations = db.execute(query).all()

    if not locations:
        return None

    nearest_distance = None

    for latitude, longitude in locations:
        distance = _haversine_distance_km(
            pickup_latitude,
            pickup_longitude,
            latitude,
            longitude,
        )

        if (
            nearest_distance is None
            or distance < nearest_distance
        ):
            nearest_distance = distance

    if nearest_distance is None:
        return None

    return nearest_distance.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def calculate_order_dynamic_pricing(
    db: Session,
    *,
    city: City,
    branch: Branch | None,
    pickup_latitude: float,
    pickup_longitude: float,
    factor_inputs: dict | None = None,
) -> dict:
    """
    Рассчитывает динамический коэффициент для нового заказа.

    Учитываются:
    - настройки филиала или города;
    - ближайший свободный водитель с GPS не старше 10 минут;
    - максимальный коэффициент;
    - дополнительные факторы только при наличии
      фактически переданных значений.

    Неизвестные значения погоды, пробок и спроса
    автоматически не подставляются.
    """

    settings_row, settings_scope = _get_effective_settings(
        db,
        city,
        branch,
    )

    values = _settings_values(settings_row)

    driver_distance = _find_nearest_available_driver_distance(
        db,
        city=city,
        branch=branch,
        pickup_latitude=pickup_latitude,
        pickup_longitude=pickup_longitude,
    )

    factor_inputs = factor_inputs or {}

    factor_names = (
        "weather",
        "traffic",
        "demand",
        "other",
    )

    effective_additions = {}

    for name in factor_names:
        enabled = values[f"{name}_enabled"]
        supplied_value = factor_inputs.get(name)

        if enabled and supplied_value is not None:
            addition = Decimal(str(supplied_value))
        else:
            addition = Decimal("0")

        if addition < 0:
            raise ValueError(
                f"Надбавка фактора {name} не может быть отрицательной"
            )

        effective_additions[name] = addition

    result = calculate_dynamic_multiplier(
        driver_distance_km=driver_distance,
        weather_addition=effective_additions["weather"],
        traffic_addition=effective_additions["traffic"],
        demand_addition=effective_additions["demand"],
        other_addition=effective_additions["other"],
        max_multiplier=values["max_multiplier"],
        driver_radius_km=values["driver_radius_km"],
        driver_distance_start_multiplier=(
            values["driver_distance_start_multiplier"]
        ),
        driver_distance_threshold_km=(
            values["driver_distance_threshold_km"]
        ),
        driver_distance_threshold_multiplier=(
            values["driver_distance_threshold_multiplier"]
        ),
        driver_distance_step_km=(
            values["driver_distance_step_km"]
        ),
        driver_distance_step_multiplier=(
            values["driver_distance_step_multiplier"]
        ),
        is_active=values["is_active"],
    )

    reasons = []

    if values["is_active"]:
        if driver_distance is None:
            reasons.append(
                "Нет свободных водителей с актуальным GPS"
            )
        elif driver_distance > values["driver_radius_km"]:
            reasons.append(
                "Ближайший свободный водитель находится "
                "за пределами первого радиуса"
            )

        for name, addition in effective_additions.items():
            if addition > 0:
                reasons.append(
                    f"Дополнительный фактор: {name}"
                )

        if result.total_multiplier >= result.max_multiplier:
            reasons.append(
                "Достигнут установленный максимальный коэффициент"
            )

    if not reasons:
        reasons.append(
            "Повышение стоимости не применяется"
        )

    settings_snapshot = {
        "scope": settings_scope,
        "id": (
            str(settings_row.id)
            if settings_row is not None
            else None
        ),
        "city_id": str(city.id),
        "branch_id": (
            str(branch.id)
            if branch is not None
            else None
        ),
        "max_multiplier": str(values["max_multiplier"]),
        "driver_radius_km": str(values["driver_radius_km"]),
        "driver_distance_start_multiplier": str(
            values["driver_distance_start_multiplier"]
        ),
        "driver_distance_threshold_km": str(
            values["driver_distance_threshold_km"]
        ),
        "driver_distance_threshold_multiplier": str(
            values["driver_distance_threshold_multiplier"]
        ),
        "driver_distance_step_km": str(
            values["driver_distance_step_km"]
        ),
        "driver_distance_step_multiplier": str(
            values["driver_distance_step_multiplier"]
        ),
        "is_active": values["is_active"],
    }

    return {
        "settings_id": (
            settings_row.id
            if settings_row is not None
            else None
        ),
        "driver_distance_km": result.driver_distance_km,
        "driver_multiplier": result.driver_multiplier,
        "total_multiplier": result.total_multiplier,
        "max_multiplier": result.max_multiplier,
        "weather_addition": result.weather_addition,
        "traffic_addition": result.traffic_addition,
        "demand_addition": result.demand_addition,
        "other_addition": result.other_addition,
        "breakdown": {
            "multiplier": str(result.total_multiplier),
            "driver_multiplier": str(result.driver_multiplier),
            "driver_distance_km": (
                str(result.driver_distance_km)
                if result.driver_distance_km is not None
                else None
            ),
            "max_multiplier": str(result.max_multiplier),
            "factors": {
                name: str(value)
                for name, value in effective_additions.items()
            },
            "reasons": reasons,
            "settings": settings_snapshot,
            "calculated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        },
    }
