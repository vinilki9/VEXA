
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class FareResult:
    base_price_kopecks: int
    distance_price_kopecks: int
    time_price_kopecks: int
    fare_limit_adjustment_kopecks: int
    total_price_kopecks: int
    included_km: Decimal = Decimal("0")
    included_minutes: Decimal = Decimal("0")
    charged_distance_km: Decimal = Decimal("0")
    charged_duration_minutes: Decimal = Decimal("0")


def calculate_fare(
    *,
    base_price_kopecks: int,
    price_per_km_kopecks: int,
    price_per_minute_kopecks: int,
    distance_km: Decimal,
    duration_minutes: Decimal,
    minimum_fare_kopecks: int | None = None,
    maximum_fare_kopecks: int | None = None,
    included_km: Decimal = Decimal("0"),
    included_minutes: Decimal = Decimal("0"),
) -> FareResult:
    prices = (
        base_price_kopecks,
        price_per_km_kopecks,
        price_per_minute_kopecks,
    )

    if any(value < 0 for value in prices):
        raise ValueError("Tariff prices cannot be negative")

    if (
        minimum_fare_kopecks is not None
        and minimum_fare_kopecks < 0
    ):
        raise ValueError("Minimum fare cannot be negative")

    if (
        maximum_fare_kopecks is not None
        and maximum_fare_kopecks < 0
    ):
        raise ValueError("Maximum fare cannot be negative")

    if (
        minimum_fare_kopecks is not None
        and maximum_fare_kopecks is not None
        and maximum_fare_kopecks < minimum_fare_kopecks
    ):
        raise ValueError(
            "Maximum fare cannot be lower than minimum fare"
        )

    if (
        not isinstance(distance_km, Decimal)
        or not distance_km.is_finite()
    ):
        raise ValueError("Distance must be a finite Decimal")

    if (
        not isinstance(duration_minutes, Decimal)
        or not duration_minutes.is_finite()
    ):
        raise ValueError("Duration must be a finite Decimal")

    if distance_km < 0 or duration_minutes < 0:
        raise ValueError("Route values cannot be negative")

    for name, value in (("included_km", included_km), ("included_minutes", included_minutes)):
        if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
            raise ValueError(f"{name} must be a finite nonnegative Decimal")

    charged_distance = max(Decimal("0"), distance_km - included_km)
    charged_duration = max(Decimal("0"), duration_minutes - included_minutes)

    distance_price = int(
        (
            Decimal(price_per_km_kopecks) * charged_distance
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

    time_price = int(
        (
            Decimal(price_per_minute_kopecks) * charged_duration
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

    # Стоимость поездки без дополнительных доплат.
    raw_trip_price = (
        base_price_kopecks
        + distance_price
        + time_price
    )

    limited_trip_price = raw_trip_price

    # Применяем минимальную стоимость.
    if minimum_fare_kopecks is not None:
        limited_trip_price = max(
            limited_trip_price,
            minimum_fare_kopecks,
        )

    # Применяем максимальную стоимость.
    if maximum_fare_kopecks is not None:
        limited_trip_price = min(
            limited_trip_price,
            maximum_fare_kopecks,
        )

    # Корректировка показывает влияние минимального
    # или максимального ограничения на итог поездки.
    fare_limit_adjustment = (
        limited_trip_price - raw_trip_price
    )

    return FareResult(
        base_price_kopecks=base_price_kopecks,
        distance_price_kopecks=distance_price,
        time_price_kopecks=time_price,
        fare_limit_adjustment_kopecks=fare_limit_adjustment,
        total_price_kopecks=limited_trip_price,
        included_km=included_km,
        included_minutes=included_minutes,
        charged_distance_km=charged_distance,
        charged_duration_minutes=charged_duration,
    )
