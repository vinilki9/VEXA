
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


ANONYMOUS_SURCHARGE_KOPECKS = 10_000


@dataclass(frozen=True)
class FareResult:
    base_price_kopecks: int
    distance_price_kopecks: int
    time_price_kopecks: int
    anonymous_surcharge_kopecks: int
    total_price_kopecks: int


def calculate_fare(
    *,
    base_price_kopecks: int,
    price_per_km_kopecks: int,
    price_per_minute_kopecks: int,
    distance_km: Decimal,
    duration_minutes: Decimal,
    anonymous: bool = False,
) -> FareResult:
    if base_price_kopecks < 0:
        raise ValueError("Base price cannot be negative")

    if price_per_km_kopecks < 0:
        raise ValueError("Distance price cannot be negative")

    if price_per_minute_kopecks < 0:
        raise ValueError("Time price cannot be negative")

    if distance_km < 0 or duration_minutes < 0:
        raise ValueError("Route values cannot be negative")

    distance_price = int(
        (
            Decimal(price_per_km_kopecks) * distance_km
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )

    time_price = int(
        (
            Decimal(price_per_minute_kopecks) * duration_minutes
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )

    anonymous_surcharge = (
        ANONYMOUS_SURCHARGE_KOPECKS if anonymous else 0
    )

    total = (
        base_price_kopecks
        + distance_price
        + time_price
        + anonymous_surcharge
    )

    return FareResult(
        base_price_kopecks=base_price_kopecks,
        distance_price_kopecks=distance_price,
        time_price_kopecks=time_price,
        anonymous_surcharge_kopecks=anonymous_surcharge,
        total_price_kopecks=total,
    )
