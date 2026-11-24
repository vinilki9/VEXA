
from abc import ABC, abstractmethod
from math import isfinite

from app.routing import (
    RouteResult,
    RoutingError,
    get_driving_route,
)


def _validate_timeout(timeout_seconds: float) -> None:
    if (
        not isfinite(timeout_seconds)
        or timeout_seconds <= 0
        or timeout_seconds > 30
    ):
        raise ValueError("Invalid routing timeout")


class RoutingProvider(ABC):
    """Единый интерфейс маршрутизации VEXA."""

    @abstractmethod
    def get_route(
        self,
        pickup_latitude: float,
        pickup_longitude: float,
        destination_latitude: float,
        destination_longitude: float,
    ) -> RouteResult:
        raise NotImplementedError


class OSRMProvider(RoutingProvider):
    """Рабочая маршрутизация OSRM."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 8.0,
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")

        if not normalized_url:
            raise RoutingError("Не задан адрес сервера OSRM")

        _validate_timeout(timeout_seconds)

        self.base_url = normalized_url
        self.timeout_seconds = timeout_seconds

    def get_route(
        self,
        pickup_latitude: float,
        pickup_longitude: float,
        destination_latitude: float,
        destination_longitude: float,
    ) -> RouteResult:
        return get_driving_route(
            base_url=self.base_url,
            pickup_latitude=pickup_latitude,
            pickup_longitude=pickup_longitude,
            destination_latitude=destination_latitude,
            destination_longitude=destination_longitude,
            timeout_seconds=self.timeout_seconds,
        )


class YandexProvider(RoutingProvider):
    """Адаптер для будущей интеграции Яндекс Маршрутизации."""

    def __init__(
        self,
        api_key: str,
        timeout_seconds: float = 8.0,
    ) -> None:
        _validate_timeout(timeout_seconds)
        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds

    def get_route(
        self,
        pickup_latitude: float,
        pickup_longitude: float,
        destination_latitude: float,
        destination_longitude: float,
    ) -> RouteResult:
        if not self.api_key:
            raise RoutingError(
                "Для подключения Яндекса необходим API-ключ"
            )

        raise RoutingError(
            "Интеграция API Яндекса ещё не завершена"
        )


def get_routing_provider(
    *,
    provider_name: str,
    osrm_base_url: str,
    timeout_seconds: float = 8.0,
    yandex_api_key: str = "",
) -> RoutingProvider:
    """Выбирает поставщика маршрутов по настройке сервера."""

    provider = provider_name.strip().lower()

    if provider == "osrm":
        return OSRMProvider(
            base_url=osrm_base_url,
            timeout_seconds=timeout_seconds,
        )

    if provider in {"yandex", "yandex_maps", "яндекс"}:
        return YandexProvider(
            api_key=yandex_api_key,
            timeout_seconds=timeout_seconds,
        )

    raise RoutingError(
        f"Неизвестный поставщик маршрутизации: {provider_name}"
    )
