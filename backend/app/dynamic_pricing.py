
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


def calculate_driver_distance_multiplier(
    distance_km: Decimal | None,
) -> Decimal:
    """
    Рассчитывает коэффициент по расстоянию
    до ближайшего подходящего свободного водителя.

    До 4 км: 1.0.
    Более 4 км: от 1.5 с плавным ростом до 2.0.
    На 20 км: 2.0.
    Далее: +0.2 за каждые полные 3 км.
    """

    if distance_km is None:
        return Decimal("1.0")

    if not isinstance(distance_km, Decimal):
        distance_km = Decimal(str(distance_km))

    if not distance_km.is_finite() or distance_km < 0:
        raise ValueError("Некорректное расстояние до водителя")

    if distance_km <= DEFAULT_DRIVER_RADIUS_KM:
        return Decimal("1.0")

    if distance_km <= DRIVER_DISTANCE_THRESHOLD_KM:
        distance_range = (
            DRIVER_DISTANCE_THRESHOLD_KM
            - DEFAULT_DRIVER_RADIUS_KM
        )

        multiplier_range = (
            DRIVER_DISTANCE_THRESHOLD_MULTIPLIER
            - DRIVER_DISTANCE_START_MULTIPLIER
        )

        progress = (
            distance_km - DEFAULT_DRIVER_RADIUS_KM
        ) / distance_range

        multiplier = (
            DRIVER_DISTANCE_START_MULTIPLIER
            + progress * multiplier_range
        )

        return multiplier.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    additional_distance = (
        distance_km - DRIVER_DISTANCE_THRESHOLD_KM
    )

    completed_steps = (
        additional_distance / DRIVER_DISTANCE_STEP_KM
    ).to_integral_value(rounding=ROUND_FLOOR)

    return (
        DRIVER_DISTANCE_THRESHOLD_MULTIPLIER
        + completed_steps * DRIVER_DISTANCE_STEP_MULTIPLIER
    )


def calculate_dynamic_multiplier(
    *,
    driver_distance_km: Decimal | None = None,
    weather_addition: Decimal = Decimal("0"),
    traffic_addition: Decimal = Decimal("0"),
    demand_addition: Decimal = Decimal("0"),
    other_addition: Decimal = Decimal("0"),
    max_multiplier: Decimal = DEFAULT_MAX_MULTIPLIER,
) -> DynamicPricingResult:
    """
    Единый расчёт динамического коэффициента.

    Надбавки факторов складываются с коэффициентом
    расстояния, а общий результат ограничивается
    максимальным значением, заданным диспетчером.

    Все надбавки передаются серверными источниками
    данных или сохранёнными настройками.
    """

    values = (
        weather_addition,
        traffic_addition,
        demand_addition,
        other_addition,
        max_multiplier,
    )

    normalized = []

    for value in values:
        if not isinstance(value, Decimal):
            value = Decimal(str(value))

        if not value.is_finite():
            raise ValueError("Коэффициенты должны быть конечными числами")

        normalized.append(value)

    (
        weather_addition,
        traffic_addition,
        demand_addition,
        other_addition,
        max_multiplier,
    ) = normalized

    if any(
        value < 0
        for value in (
            weather_addition,
            traffic_addition,
            demand_addition,
            other_addition,
        )
    ):
        raise ValueError("Надбавки динамического тарифа не могут быть отрицательными")

    if max_multiplier < Decimal("1.0"):
        raise ValueError("Максимальный коэффициент не может быть ниже 1.0")

    driver_multiplier = calculate_driver_distance_multiplier(
        driver_distance_km
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
