"""VEXA opt-in included km/minutes and future audited operational charges."""
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.pricing import calculate_fare
from app.operational_pricing import calculate_operational_charge
from app.schemas import TariffCreate, TariffUpdate
from app.models import Tariff
from app.routing import RouteResult
from app.route_pricing import calculate_order_route_price


class IncludedDistanceDurationTests(unittest.TestCase):
    def fare(self, *, distance="3", duration="10", km="0", minutes="0", minimum=None, maximum=None):
        return calculate_fare(
            base_price_kopecks=5000,
            price_per_km_kopecks=2000,
            price_per_minute_kopecks=100,
            distance_km=Decimal(distance),
            duration_minutes=Decimal(duration),
            included_km=Decimal(km),
            included_minutes=Decimal(minutes),
            minimum_fare_kopecks=minimum,
            maximum_fare_kopecks=maximum,
        )

    def test_zero_inclusions_preserve_old_cost(self):
        fare = self.fare()
        self.assertEqual(fare.total_price_kopecks, 12000)
        self.assertEqual(fare.charged_distance_km, Decimal("3"))
        self.assertEqual(fare.charged_duration_minutes, Decimal("10"))

    def test_included_km_and_minutes(self):
        fare = self.fare(km="1", minutes="3")
        self.assertEqual(fare.distance_price_kopecks, 4000)
        self.assertEqual(fare.time_price_kopecks, 700)
        self.assertEqual(fare.total_price_kopecks, 9700)
        self.assertEqual(fare.charged_distance_km, Decimal("2"))
        self.assertEqual(fare.charged_duration_minutes, Decimal("7"))

    def test_route_shorter_than_included_is_base_only(self):
        fare = self.fare(distance="0.2", duration="1", km="10", minutes="30")
        self.assertEqual(fare.distance_price_kopecks, 0)
        self.assertEqual(fare.time_price_kopecks, 0)
        self.assertEqual(fare.total_price_kopecks, 5000)

    def test_included_can_be_fractional(self):
        fare = self.fare(distance="1.755", duration="5.25", km="1.125", minutes="3.25")
        self.assertEqual(fare.distance_price_kopecks, 1260)
        self.assertEqual(fare.time_price_kopecks, 200)

    def test_minimum_still_applies_after_inclusions(self):
        fare = self.fare(km="2", minutes="8", minimum=10000)
        self.assertEqual(fare.total_price_kopecks, 10000)
        self.assertEqual(fare.fare_limit_adjustment_kopecks, 2800)

    def test_maximum_still_applies_after_inclusions(self):
        fare = self.fare(distance="80", km="1", maximum=20000)
        self.assertEqual(fare.total_price_kopecks, 20000)
        self.assertTrue(fare.fare_limit_adjustment_kopecks < 0)

    def test_negative_inclusions_rejected(self):
        for value in ("-1", "-0.01"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.fare(km=value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.fare(minutes=value)

    def test_nonfinite_inclusions_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.fare(km=value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.fare(minutes=value)

    def test_non_decimal_inclusions_rejected(self):
        with self.assertRaises(ValueError):
            calculate_fare(
                base_price_kopecks=100, price_per_km_kopecks=100,
                price_per_minute_kopecks=10,
                distance_km=Decimal("1"), duration_minutes=Decimal("1"),
                included_km=0.1,  # float is forbidden in core
            )

    @patch("app.route_pricing.get_routing_provider")
    @patch("app.route_pricing.settings", SimpleNamespace(
        routing_provider="osrm", osrm_base_url="http://localhost:5000",
        routing_timeout_seconds=8.0, yandex_api_key=""))
    def test_server_route_applies_inclusions(self, mock_get_provider):
        provider = Mock()
        provider.get_route.return_value = RouteResult(
            distance_meters=Decimal("3500"), duration_seconds=Decimal("600"))
        mock_get_provider.return_value = provider
        result = calculate_order_route_price(
            pickup_latitude=54.9, pickup_longitude=37.2,
            destination_latitude=54.91, destination_longitude=37.21,
            base_price_kopecks=5000, price_per_km_kopecks=2000,
            price_per_minute_kopecks=100, included_km=Decimal("1"),
            included_minutes=Decimal("3"),
        )
        self.assertEqual(result.fare.distance_price_kopecks, 5000)
        self.assertEqual(result.fare.time_price_kopecks, 700)
        self.assertEqual(result.fare.total_price_kopecks, 10700)


class OperationalChargeTests(unittest.TestCase):
    def charge(self, *, wait="8", free="3", per_minute=200, stops=2, per_stop=500):
        return calculate_operational_charge(
            actual_wait_minutes=Decimal(wait), free_wait_minutes=Decimal(free),
            waiting_price_per_minute_kopecks=per_minute,
            extra_stops=stops, stop_price_kopecks=per_stop,
        )

    def test_waiting_and_stops(self):
        result = self.charge()
        self.assertEqual(result.chargeable_wait_minutes, Decimal("5"))
        self.assertEqual(result.waiting_charge_kopecks, 1000)
        self.assertEqual(result.stops_charge_kopecks, 1000)
        self.assertEqual(result.total_kopecks, 2000)

    def test_free_waiting_window(self):
        self.assertEqual(self.charge(wait="2", free="3", stops=0).total_kopecks, 0)

    def test_fractional_minute_rounding(self):
        self.assertEqual(self.charge(wait="3.25", per_minute=103, stops=0).waiting_charge_kopecks, 26)

    def test_no_negative_or_nonfinite_duration(self):
        for value in ("-1", "Infinity", "NaN"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.charge(wait=value)

    def test_bad_stop_or_price_rejected(self):
        for kw in ({"stops": -1}, {"per_stop": -1}, {"per_minute": -1}, {"stops": True}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.charge(**kw)


class TariffModelAndApiTests(unittest.TestCase):
    def test_create_defaults_preserve_current_prices(self):
        t = TariffCreate(city_code="example", code="standard", name="Standard",
                         vehicle_class="economy", base_price_kopecks=100,
                         price_per_km_kopecks=200, price_per_minute_kopecks=10)
        self.assertEqual(t.included_km, Decimal("0"))
        self.assertEqual(t.included_minutes, Decimal("0"))
        self.assertEqual(t.free_wait_minutes, Decimal("0"))
        self.assertEqual(t.stop_price_kopecks, 0)

    def test_invalid_tariff_policies_rejected(self):
        from pydantic import ValidationError
        for key, value in (("included_km", -1), ("included_minutes", -0.1),
                           ("free_wait_minutes", -1),
                           ("waiting_price_per_minute_kopecks", -1), ("stop_price_kopecks", -1)):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                TariffUpdate(**{key: value})

    def test_inclusions_have_db_columns(self):
        for field in ("included_km", "included_minutes", "free_wait_minutes",
                      "waiting_price_per_minute_kopecks", "stop_price_kopecks"):
            self.assertIn(field, Tariff.__table__.columns)
            self.assertFalse(Tariff.__table__.columns[field].nullable)


if __name__ == "__main__":
    unittest.main()
