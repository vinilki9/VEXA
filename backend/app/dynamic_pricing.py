
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP


DEFAULT_MAX_MULTIPLIER = Decimal("2.5")
DEFAULT_DRIVER_RADIUS_KM = Decimal("4.0")
DRIVER_DISTANCE_START_MULTIPLIER = Decimal("1.5")
DRIVER_DISTANCE_THRESHOLD_KM = Decimal("20.0")
DRIVER_DISTANCE_THRESHOLD_MULTIPLIER = Decimal("2.0")
DRIVER_DISTANCE_STEP_KM = Decimal("3.0")
DRIVER_DISTANCE_STEP_MULTIPLIER = Decimal("0.2")


@dataclass(frozen=True)
class DynamicPricingResult:
    driver_distance_km: Decimal | None
    driver_multiplier: Decimal
    weather_addition: Decimal
    traffic_addition: Decimal
    demand_addition: Decimal
    other_addition: Decimal
    total_multiplier: Decimal
    max_multiplier: Decimal


def _to_decimal(value, field_name: str) -> Decimal:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))

    if not value.is_finite():
        raise ValueError(
            f"{field_name} должен быть конечным числом"
        )

    return value


def calculate_driver_distance_multiplier(
    distance_km: Decimal | None,
    *,
    driver_radius_km: Decimal = DEFAULT_DRIVER_RADIUS_KM,
    start_multiplier: Decimal = DRIVER_DISTANCE_START_MULTIPLIER,
    threshold_km: Decimal = DRIVER_DISTANCE_THRESHOLD_KM,
    threshold_multiplier: Decimal = DRIVER_DISTANCE_THRESHOLD_MULTIPLIER,
    step_km: Decimal = DRIVER_DISTANCE_STEP_KM,
    step_multiplier: Decimal = DRIVER_DISTANCE_STEP_MULTIPLIER,
) -> Decimal:
    """
    Рассчитывает коэффициент по расстоянию до ближайшего
    подходящего свободного водителя.

    До установленного радиуса включительно: 1.0.
    Если свободного водителя нет в радиусе: от 1.5.
    На пороге 20 км: 2.0.
    Далее: +0.2 за каждые полные 3 км.

    Все параметры могут поступать из настроек города
    или филиала.
    """

    driver_radius_km = _to_decimal(
        driver_radius_km,
        "driver_radius_km",
    )
    start_multiplier = _to_decimal(
        start_multiplier,
        "start_multiplier",
    )
    threshold_km = _to_decimal(
        threshold_km,
        "threshold_km",
    )
    threshold_multiplier = _to_decimal(
        threshold_multiplier,
        "threshold_multiplier",
    )
    step_km = _to_decimal(
        step_km,
        "step_km",
    )
    step_multiplier = _to_decimal(
        step_multiplier,
        "step_multiplier",
    )

    if driver_radius_km < 0:
        raise ValueError("Радиус водителя не может быть отрицательным")

    if threshold_km <= driver_radius_km:
        raise ValueError(
            "Порог расстояния должен быть больше радиуса водителя"
        )

    if start_multiplier < Decimal("1.0"):
        raise ValueError(
            "Начальный коэффициент не может быть ниже 1.0"
        )

    if threshold_multiplier < start_multiplier:
        raise ValueError(
            "Коэффициент на пороге не может быть меньше начального"
        )

    if step_km <= 0:
        raise ValueError(
            "Шаг расстояния должен быть больше нуля"
        )

    if step_multiplier < 0:
        raise ValueError(
            "Шаг коэффициента не может быть отрицательным"
        )

    # Нет подходящего свободного водителя с актуальным GPS.
    # Считаем, что водитель находится за пределами первого радиуса.
    if distance_km is None:
        return start_multiplier

    distance_km = _to_decimal(
        distance_km,
        "distance_km",
    )

    if distance_km < 0:
        raise ValueError(
            "Расстояние до водителя не может быть отрицательным"
        )

    if distance_km <= driver_radius_km:
        return Decimal("1.0")

    if distance_km <= threshold_km:
        distance_range = threshold_km - driver_radius_km
        multiplier_range = (
            threshold_multiplier - start_multiplier
        )

        progress = (
            distance_km - driver_radius_km
        ) / distance_range

        multiplier = (
            start_multiplier
            + progress * multiplier_range
        )

        return multiplier.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    additional_distance = distance_km - threshold_km

    completed_steps = (
        additional_distance / step_km
    ).to_integral_value(
        rounding=ROUND_FLOOR,
    )

    return (
        threshold_multiplier
        + completed_steps * step_multiplier
    )


def calculate_dynamic_multiplier(
    *,
    driver_distance_km: Decimal | None = None,
    weather_addition: Decimal = Decimal("0"),
    traffic_addition: Decimal = Decimal("0"),
    demand_addition: Decimal = Decimal("0"),
    other_addition: Decimal = Decimal("0"),
    max_multiplier: Decimal = DEFAULT_MAX_MULTIPLIER,
    driver_radius_km: Decimal = DEFAULT_DRIVER_RADIUS_KM,
    driver_distance_start_multiplier: Decimal = DRIVER_DISTANCE_START_MULTIPLIER,
    driver_distance_threshold_km: Decimal = DRIVER_DISTANCE_THRESHOLD_KM,
    driver_distance_threshold_multiplier: Decimal = DRIVER_DISTANCE_THRESHOLD_MULTIPLIER,
    driver_distance_step_km: Decimal = DRIVER_DISTANCE_STEP_KM,
    driver_distance_step_multiplier: Decimal = DRIVER_DISTANCE_STEP_MULTIPLIER,
    is_active: bool = True,
) -> DynamicPricingResult:
    """
    Единый расчёт динамического коэффициента.

    Параметры расстояния и максимальный коэффициент
    передаются из настроек города или филиала.

    Надбавки факторов складываются с коэффициентом
    расстояния.

    Общий результат ограничивается максимальным
    значением, заданным диспетчером.

    Если динамическое ценообразование отключено,
    возвращается нейтральный коэффициент 1.0.
    """

    if driver_distance_km is not None:
        driver_distance_km = _to_decimal(
            driver_distance_km,
            "driver_distance_km",
        )

    weather_addition = _to_decimal(
        weather_addition,
        "weather_addition",
    )
    traffic_addition = _to_decimal(
        traffic_addition,
        "traffic_addition",
    )
    demand_addition = _to_decimal(
        demand_addition,
        "demand_addition",
    )
    other_addition = _to_decimal(
        other_addition,
        "other_addition",
    )
    max_multiplier = _to_decimal(
        max_multiplier,
        "max_multiplier",
    )

    if max_multiplier < Decimal("1.0"):
        raise ValueError(
            "Максимальный коэффициент не может быть ниже 1.0"
        )

    additions = (
        weather_addition,
        traffic_addition,
        demand_addition,
        other_addition,
    )

    if any(value < 0 for value in additions):
        raise ValueError(
            "Надбавки динамического тарифа не могут быть отрицательными"
        )

    if not is_active:
        return DynamicPricingResult(
            driver_distance_km=driver_distance_km,
            driver_multiplier=Decimal("1.0"),
            weather_addition=Decimal("0"),
            traffic_addition=Decimal("0"),
            demand_addition=Decimal("0"),
            other_addition=Decimal("0"),
            total_multiplier=Decimal("1.0"),
            max_multiplier=max_multiplier,
        )

    driver_multiplier = calculate_driver_distance_multiplier(
        driver_distance_km,
        driver_radius_km=driver_radius_km,
        start_multiplier=driver_distance_start_multiplier,
        threshold_km=driver_distance_threshold_km,
        threshold_multiplier=driver_distance_threshold_multiplier,
        step_km=driver_distance_step_km,
        step_multiplier=driver_distance_step_multiplier,
    )

    raw_multiplier = (
        driver_multiplier
        + weather_addition
        + traffic_addition
        + demand_addition
        + other_addition
    )

    total_multiplier = min(
        raw_multiplier,
        max_multiplier,
    )

    return DynamicPricingResult(
        driver_distance_km=driver_distance_km,
        driver_multiplier=driver_multiplier,
        weather_addition=weather_addition,
        traffic_addition=traffic_addition,
        demand_addition=demand_addition,
        other_addition=other_addition,
        total_multiplier=total_multiplier,
        max_multiplier=max_multiplier,
    )
