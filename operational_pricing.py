"""Optional, deterministic operational charges (NOT automatic settlement).

These prices may only be applied after verified stop / waiting events,
appropriate business rules, passenger disclosure, and audited persistence.
All amounts are integer kopecks; all durations are Decimal minutes.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class OperationalCharge:
    chargeable_wait_minutes: Decimal
    waiting_charge_kopecks: int
    stops_charge_kopecks: int
    total_kopecks: int


def calculate_operational_charge(
    *,
    actual_wait_minutes: Decimal,
    free_wait_minutes: Decimal,
    waiting_price_per_minute_kopecks: int,
    extra_stops: int,
    stop_price_kopecks: int,
) -> OperationalCharge:
    for label, value in (("actual_wait_minutes", actual_wait_minutes), ("free_wait_minutes", free_wait_minutes)):
        if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
            raise ValueError(f"Invalid {label}")
    for label, value in (("waiting_price_per_minute_kopecks", waiting_price_per_minute_kopecks), ("extra_stops", extra_stops), ("stop_price_kopecks", stop_price_kopecks)):
        if type(value) is not int or value < 0:
            raise ValueError(f"Invalid {label}")
    charged = max(Decimal("0"), actual_wait_minutes - free_wait_minutes)
    waiting = int((charged * waiting_price_per_minute_kopecks).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    stops = extra_stops * stop_price_kopecks
    return OperationalCharge(charged, waiting, stops, waiting + stops)
