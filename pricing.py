
from app.models import Tariff


ANONYMOUS_SURCHARGE_KOPECKS = 10_000


def calculate_order_price(
    tariff: Tariff,
    distance_meters: int,
    duration_seconds: int,
    extras_kopecks: int = 0,
    anonymous: bool = False,
) -> dict:
    """
    Calculate an order price using trusted server-side route data.

    Distance and duration must come from the backend routing service,
    never directly from unverified client input.
    """

    if not tariff.is_active:
        raise ValueError("Tariff is inactive")

    values = (
        tariff.base_price_kopecks,
        tariff.price_per_km_kopecks,
        tariff.price_per_minute_kopecks,
        distance_meters,
        duration_seconds,
        extras_kopecks,
    )

    if any(value is None or value < 0 for value in values):
        raise ValueError("Price and route values must be non-negative")

    # Calculate proportionally and round to the nearest kopeck.
    distance_kopecks = (
        tariff.price_per_km_kopecks * distance_meters + 500
    ) // 1000

    time_kopecks = (
        tariff.price_per_minute_kopecks * duration_seconds + 30
    ) // 60

    anonymous_surcharge = (
        ANONYMOUS_SURCHARGE_KOPECKS if anonymous else 0
    )

    base_kopecks = tariff.base_price_kopecks

    total_kopecks = (
        base_kopecks
        + distance_kopecks
        + time_kopecks
        + extras_kopecks
        + anonymous_surcharge
    )

    return {
        "base_kopecks": base_kopecks,
        "distance_kopecks": distance_kopecks,
        "time_kopecks": time_kopecks,
        "extras_kopecks": extras_kopecks,
        "anonymous_surcharge_kopecks": anonymous_surcharge,
        "total_kopecks": total_kopecks,
        "calculation_details": {
            "distance_meters": distance_meters,
            "duration_seconds": duration_seconds,
            "anonymous": anonymous,
        },
    }
