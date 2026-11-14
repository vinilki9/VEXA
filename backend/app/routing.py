
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import isfinite
from urllib.error import URLError
from urllib.request import urlopen
from urllib.parse import urlencode


class RoutingError(Exception):
    """Ошибка получения автомобильного маршрута."""


@dataclass(frozen=True)
class RouteResult:
    distance_meters: Decimal
    duration_seconds: Decimal

    @property
    def distance_km(self) -> Decimal:
        return self.distance_meters / Decimal("1000")

    @property
    def duration_minutes(self) -> Decimal:
        return self.duration_seconds / Decimal("60")


def _validate_coordinate(value: float, minimum: float, maximum: float) -> None:
    if not isfinite(value) or not minimum <= value <= maximum:
        raise ValueError("Invalid geographic coordinate")


def get_driving_route(
    *,
    base_url: str,
    pickup_latitude: float,
    pickup_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
    timeout_seconds: float = 8.0,
) -> RouteResult:
    _validate_coordinate(pickup_latitude, -90, 90)
    _validate_coordinate(destination_latitude, -90, 90)
    _validate_coordinate(pickup_longitude, -180, 180)
    _validate_coordinate(destination_longitude, -180, 180)

    if not isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("Invalid routing timeout")

    normalized_url = base_url.strip().rstrip("/")

    if not normalized_url:
        raise ValueError("OSRM base URL is required")

    coordinates = (
        f"{pickup_longitude},{pickup_latitude};"
        f"{destination_longitude},{destination_latitude}"
    )

    query = urlencode({
        "overview": "false",
        "steps": "false",
    })

    url = (
        f"{normalized_url}/route/v1/driving/"
        f"{coordinates}?{query}"
    )

    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))

    except (URLError, TimeoutError, OSError) as exc:
        raise RoutingError("OSRM service is unavailable") from exc

    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RoutingError("OSRM returned invalid data") from exc

    if not isinstance(payload, dict) or payload.get("code") != "Ok":
        raise RoutingError("OSRM could not calculate the route")

    routes = payload.get("routes")

    if not isinstance(routes, list) or not routes:
        raise RoutingError("OSRM returned no routes")

    route = routes[0]

    try:
        distance = Decimal(str(route["distance"]))
        duration = Decimal(str(route["duration"]))
    except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
        raise RoutingError("OSRM route data is incomplete") from exc

    if (
        not distance.is_finite()
        or not duration.is_finite()
        or distance < 0
        or duration < 0
    ):
        raise RoutingError("OSRM returned invalid route values")

    return RouteResult(
        distance_meters=distance,
        duration_seconds=duration,
    )
