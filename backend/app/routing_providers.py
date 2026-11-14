
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from app.routing import (
    RouteResult,
    RoutingError,
    get_driving_route,
)


@dataclass(frozen=True)
class RouteRequest:
    pickup_latitude: float
    pickup_longitude: float
    destination_latitude: float
    destination_longitude: float


class RoutingProvider(ABC):
    """Общий интерфейс поставщиков маршрутизации VEXA."""

    @abstractmethod
    def get_route(self, request: RouteRequest) -> RouteResult:
        """Возвращает расстояние и время автомобильного маршрута."""
        raise NotImplementedError


class OSRMProvider(RoutingProvider):
    """Рабочий поставщик маршрутов OSRM."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 8.0,
    ) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def get_route(self, request: RouteRequest) -> RouteResult:
        return get_driving_route(
            base_url=self.base_url,
            pickup_latitude=request.pickup_latitude,
            pickup_longitude=request.pickup_longitude,
            destination_latitude=request.destination_latitude,
            destination_longitude=request.destination_longitude,
            timeout_seconds=self.timeout_seconds,
        )


class TwoGISProvider(RoutingProvider):
    """
    Адаптер 2ГИС.

    Интерфейс совместим с OSRM.
    Реальный HTTP-запрос к API 2ГИС будет добавлен
    после настройки API-ключа и параметров API.
    """

    def __init__(
        self,
        api_key: str,
        timeout_seconds: float = 8.0,
    ) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def get_route(self, request: RouteRequest) -> RouteResult:
        if not self.api_key.strip():
            raise RoutingError(
                "Для подключения 2ГИС необходим API-ключ"
            )

        raise RoutingError(
            "Провайдер 2ГИС пока не настроен. "
            "Используйте OSRM до завершения интеграции."
        )


def get_routing_provider(
    *,
    provider_name: str,
    osrm_base_url: str,
    osrm_timeout_seconds: float = 8.0,
    two_gis_api_key: str = "",
) -> RoutingProvider:
    """
    Выбирает поставщика маршрутизации по настройке сервера.

    Допустимые значения:
    - osrm
    - 2gis

    Переключение не требует изменения приложений.
    """

    provider = provider_name.strip().lower()

    if provider == "osrm":
        if not osrm_base_url.strip():
            raise RoutingError(
                "Не задан адрес сервера OSRM"
            )

        return OSRMProvider(
            base_url=osrm_base_url,
            timeout_seconds=osrm_timeout_seconds,
        )

    if provider in {"2gis", "two_gis", "2гис"}:
        return TwoGISProvider(
            api_key=two_gis_api_key,
            timeout_seconds=osrm_timeout_seconds,
        )

    raise RoutingError(
        f"Неизвестный поставщик маршрутизации: {provider_name}"
    )
