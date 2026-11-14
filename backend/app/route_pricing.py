
from dataclasses import dataclass
from decimal import Decimal

from app.config import settings
from app.pricing import FareResult, calculate_fare
from app.routing import RouteResult, RoutingError
from app.routing_providers import get_routing_provider


@dataclass(frozen=True)
class OrderRoutePricing:
    route: RouteResult
    fare: FareResult
    provider_name: str


def calculate_order_route_price(
    *,
    pickup_latitude: float,
    pickup_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
    base_price_kopecks: int,
    price_per_km_kopecks: int,
    price_per_minute_kopecks: int,
    anonymous: bool,
) -> OrderRoutePricing:
    """
    Получает маршрут у выбранного поставщика
    и рассчитывает стоимость заказа на сервере.

    Клиентские расстояние, время и стоимость
    не используются.
    """

    provider_name = settings.routing_provider.strip().lower()

    provider = get_routing_provider(
        provider_name=provider_name,
        osrm_base_url=settings.osrm_base_url,
        timeout_seconds=settings.routing_timeout_seconds,
        two_gis_api_key=settings.two_gis_api_key,
        yandex_api_key=settings.yandex_api_key,
    )

    try:
        route = provider.get_route(
            pickup_latitude=pickup_latitude,
            pickup_longitude=pickup_longitude,
            destination_latitude=destination_latitude,
            destination_longitude=destination_longitude,
        )

    except RoutingError:
        raise

    except (ValueError, TypeError) as exc:
        raise RoutingError(
            "Некорректные координаты маршрута"
        ) from exc

    fare = calculate_fare(
        base_price_kopecks=base_price_kopecks,
        price_per_km_kopecks=price_per_km_kopecks,
        price_per_minute_kopecks=price_per_minute_kopecks,
        distance_km=route.distance_km,
        duration_minutes=route.duration_minutes,
        anonymous=anonymous,
    )

    return OrderRoutePricing(
        route=route,
        fare=fare,
        provider_name=provider_name,
    )
