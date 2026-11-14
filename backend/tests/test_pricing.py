
import unittest
from decimal import Decimal

from app.pricing import calculate_fare


class CalculateFareTests(unittest.TestCase):
    def test_base_price_only(self):
        result = calculate_fare(
            base_price_kopecks=5000,
            price_per_km_kopecks=0,
            price_per_minute_kopecks=0,
            distance_km=Decimal("0"),
            duration_minutes=Decimal("0"),
        )
        self.assertEqual(result.total_price_kopecks, 5000)

    def test_distance_and_time(self):
        result = calculate_fare(
            base_price_kopecks=5000,
            price_per_km_kopecks=2000,
            price_per_minute_kopecks=100,
            distance_km=Decimal("3"),
            duration_minutes=Decimal("10"),
        )
        self.assertEqual(result.distance_price_kopecks, 6000)
        self.assertEqual(result.time_price_kopecks, 1000)
        self.assertEqual(result.total_price_kopecks, 12000)

    def test_anonymous_surcharge(self):
        result = calculate_fare(
            base_price_kopecks=5000,
            price_per_km_kopecks=0,
            price_per_minute_kopecks=0,
            distance_km=Decimal("0"),
            duration_minutes=Decimal("0"),
            anonymous=True,
        )
        self.assertEqual(result.anonymous_surcharge_kopecks, 10000)
        self.assertEqual(result.total_price_kopecks, 15000)

    def test_fractional_distance_rounding(self):
        result = calculate_fare(
            base_price_kopecks=0,
            price_per_km_kopecks=1000,
            price_per_minute_kopecks=0,
            distance_km=Decimal("1.25"),
            duration_minutes=Decimal("0"),
        )
        self.assertEqual(result.distance_price_kopecks, 1250)

    def test_negative_distance_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_fare(
                base_price_kopecks=5000,
                price_per_km_kopecks=1000,
                price_per_minute_kopecks=100,
                distance_km=Decimal("-1"),
                duration_minutes=Decimal("0"),
            )


if __name__ == "__main__":
    unittest.main()
