
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.route_pricing import calculate_order_route_price
from app.routing import RouteResult, RoutingError


class CalculateOrderRoutePriceTests(unittest.TestCase):
    @patch("app.route_pricing.get_routing_provider")
    @patch(
        "app.route_pricing.settings",
        SimpleNamespace(
            routing_provider=" OSRM ",
            osrm_base_url="http://localhost:5000",
            routing_timeout_seconds=8.0,
            yandex_api_key="",
        ),
    )
    def test_calculates_fare_from_server_route(
        self,
        get_provider,
    ):
        provider = Mock()
        provider.get_route.return_value = RouteResult(
            distance_meters=Decimal("2500"),
            duration_seconds=Decimal("600"),
        )
        get_provider.return_value = provider

        result = calculate_order_route_price(
            pickup_latitude=54.9,
            pickup_longitude=37.2,
            destination_latitude=54.91,
            destination_longitude=37.21,
            base_price_kopecks=5000,
            price_per_km_kopecks=2000,
            price_per_minute_kopecks=100,
        )

        self.assertEqual(result.provider_name, "osrm")
        self.assertEqual(result.route.distance_meters, Decimal("2500"))
        self.assertEqual(result.route.duration_seconds, Decimal("600"))
        self.assertEqual(result.fare.base_price_kopecks, 5000)
        self.assertEqual(result.fare.distance_price_kopecks, 5000)
        self.assertEqual(result.fare.time_price_kopecks, 1000)
        self.assertEqual(result.fare.total_price_kopecks, 11000)
        get_provider.assert_called_once_with(
            provider_name="osrm",
            osrm_base_url="http://localhost:5000",
            timeout_seconds=8.0,
            yandex_api_key="",
        )
        provider.get_route.assert_called_once_with(
            pickup_latitude=54.9,
            pickup_longitude=37.2,
            destination_latitude=54.91,
            destination_longitude=37.21,
        )

    @patch("app.route_pricing.get_routing_provider")
    @patch(
        "app.route_pricing.settings",
        SimpleNamespace(
            routing_provider="osrm",
            osrm_base_url="http://localhost:5000",
            routing_timeout_seconds=8.0,
            yandex_api_key="",
        ),
    )
    def test_routing_error_is_propagated(self, get_provider):
        provider = Mock()
        provider.get_route.side_effect = RoutingError(
            "OSRM service is unavailable"
        )
        get_provider.return_value = provider

        with self.assertRaises(RoutingError):
            calculate_order_route_price(
                pickup_latitude=54.9,
                pickup_longitude=37.2,
                destination_latitude=54.91,
                destination_longitude=37.21,
                base_price_kopecks=5000,
                price_per_km_kopecks=2000,
                price_per_minute_kopecks=100,
            )

    @patch("app.route_pricing.get_routing_provider")
    @patch(
        "app.route_pricing.settings",
        SimpleNamespace(
            routing_provider="osrm",
            osrm_base_url="http://localhost:5000",
            routing_timeout_seconds=8.0,
            yandex_api_key="",
        ),
    )
    def test_invalid_route_data_becomes_routing_error(
        self,
        get_provider,
    ):
        provider = Mock()
        provider.get_route.side_effect = ValueError(
            "Invalid coordinates"
        )
        get_provider.return_value = provider

        with self.assertRaises(RoutingError):
            calculate_order_route_price(
                pickup_latitude=54.9,
                pickup_longitude=37.2,
                destination_latitude=54.91,
                destination_longitude=37.21,
                base_price_kopecks=5000,
                price_per_km_kopecks=2000,
                price_per_minute_kopecks=100,
            )

    @patch("app.route_pricing.get_routing_provider")
    @patch(
        "app.route_pricing.settings",
        SimpleNamespace(
            routing_provider="osrm",
            osrm_base_url="http://localhost:5000",
            routing_timeout_seconds=8.0,
            yandex_api_key="",
        ),
    )
    def test_calculates_fare_without_extra_surcharge(
        self,
        get_provider,
    ):
        provider = Mock()
        provider.get_route.return_value = RouteResult(
            distance_meters=Decimal("2500"),
            duration_seconds=Decimal("600"),
        )
        get_provider.return_value = provider

        result = calculate_order_route_price(
            pickup_latitude=54.9,
            pickup_longitude=37.2,
            destination_latitude=54.91,
            destination_longitude=37.21,
            base_price_kopecks=5000,
            price_per_km_kopecks=2000,
            price_per_minute_kopecks=100,
        )

        self.assertEqual(
            result.fare.total_price_kopecks,
            11000,
        )


if __name__ == "__main__":
    unittest.main()
