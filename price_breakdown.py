"""Transparent, deterministic breakdown of a VEXA price quote.

Amounts are integer kopecks. This does not change any tariff, multiplier,
commission or the authoritative server-side price calculation.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


LINE_FIELDS = (
    ("fare_base_price_kopecks", "base", "Подача и базовая стоимость"),
    ("fare_distance_price_kopecks", "distance", "Расстояние"),
    ("fare_time_price_kopecks", "time", "Время в пути"),
    ("fare_limit_adjustment_kopecks", "fare_limit", "Минимум / максимум тарифа"),
    ("fare_dynamic_adjustment_kopecks", "dynamic", "Коэффициент спроса"),
    ("child_seat_surcharge_kopecks", "child_seat", "Детское кресло"),
    ("animal_transport_surcharge_kopecks", "animals", "Перевозка животного"),
    ("cargo_vehicle_surcharge_kopecks", "cargo_vehicle", "Грузовой автомобиль"),
    ("cargo_loaders_surcharge_kopecks", "cargo_loaders", "Грузчики"),
)


class PriceBreakdownError(ValueError):
    """A quote contains invalid or contradictory monetary data."""


def _require_kopecks(quote: dict, field: str, *, signed: bool = False) -> int:
    value = quote.get(field)
    if type(value) is not int or (not signed and value < 0):
        raise PriceBreakdownError(f"Некорректное поле расчёта: {field}")
    return value


def build_price_breakdown(quote: dict) -> dict:
    """Validate a signed-price snapshot and return presentation-ready lines.

    Returns a subtotal before dynamic pricing and extras, each non-zero charge,
    and the exact total. Values remain kopecks (never floats).
    """
    if not isinstance(quote, dict):
        raise PriceBreakdownError("Некорректный снимок стоимости")

    lines = []
    amounts = {}
    for field, code, title in LINE_FIELDS:
        amount = _require_kopecks(
            quote,
            field,
            signed=(field == "fare_limit_adjustment_kopecks"),
        )
        amounts[field] = amount
        if amount or field == "fare_base_price_kopecks":
            lines.append({"code": code, "label": title, "amount_kopecks": amount})

    trip_price = sum(amounts[field] for field, _, _ in LINE_FIELDS[:4])
    if trip_price < 0:
        raise PriceBreakdownError("Стоимость маршрута не может быть отрицательной")

    try:
        multiplier = Decimal(str(quote["dynamic_pricing_multiplier"]))
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise PriceBreakdownError("Некорректный динамический коэффициент") from exc
    if not multiplier.is_finite() or multiplier < 1:
        raise PriceBreakdownError("Динамический коэффициент должен быть не ниже 1")

    expected_dynamic = int(
        (Decimal(trip_price) * (multiplier - Decimal("1"))).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    if amounts["fare_dynamic_adjustment_kopecks"] != expected_dynamic:
        raise PriceBreakdownError("Динамическая надбавка не совпадает с коэффициентом")

    total = _require_kopecks(quote, "price_kopecks")
    if total != sum(amounts.values()):
        raise PriceBreakdownError("Сумма компонентов не совпадает с итоговой ценой")

    rubles_rounded = _require_kopecks(quote, "price_rub")
    if rubles_rounded != (total + 50) // 100:
        raise PriceBreakdownError("Сумма в рублях не совпадает с копейками")

    return {
        "trip_subtotal_kopecks": trip_price,
        "total_kopecks": total,
        "lines": lines,
    }
