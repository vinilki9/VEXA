
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

    def test_fractional_time_rounding(self):
        result = calculate_fare(
            base_price_kopecks=0,
            price_per_km_kopecks=0,
            price_per_minute_kopecks=100,
            distance_km=Decimal("0"),
            duration_minutes=Decimal("2.5"),
        )
        self.assertEqual(result.time_price_kopecks, 250)

    def test_half_kopeck_rounds_up(self):
        result = calculate_fare(
            base_price_kopecks=0,
            price_per_km_kopecks=1,
            price_per_minute_kopecks=0,
            distance_km=Decimal("0.5"),
            duration_minutes=Decimal("0"),
        )
        self.assertEqual(result.distance_price_kopecks, 1)

    def test_negative_time_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_fare(
                base_price_kopecks=5000,
                price_per_km_kopecks=1000,
                price_per_minute_kopecks=100,
                distance_km=Decimal("0"),
                duration_minutes=Decimal("-1"),
            )

    def test_negative_tariffs_are_rejected(self):
        for base, per_km, per_minute in [
            (-1, 1000, 100),
            (5000, -1, 100),
            (5000, 1000, -1),
        ]:
            with self.subTest(
                base=base,
                per_km=per_km,
                per_minute=per_minute,
            ):
                with self.assertRaises(ValueError):
                    calculate_fare(
                        base_price_kopecks=base,
                        price_per_km_kopecks=per_km,
                        price_per_minute_kopecks=per_minute,
                        distance_km=Decimal("0"),
                        duration_minutes=Decimal("0"),
                    )
    def test_non_finite_distance_is_rejected(self):
        for distance in (
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
        ):
            with self.subTest(distance=distance):
                with self.assertRaises(ValueError):
                    calculate_fare(
                        base_price_kopecks=5000,
                        price_per_km_kopecks=1000,
                        price_per_minute_kopecks=100,
                        distance_km=distance,
                        duration_minutes=Decimal("10"),
                    )

    def test_non_finite_duration_is_rejected(self):
        for duration in (
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
        ):
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):
                    calculate_fare(
                        base_price_kopecks=5000,
                        price_per_km_kopecks=1000,
                        price_per_minute_kopecks=100,
                        distance_km=Decimal("2"),
                        duration_minutes=duration,
                    )
if __name__ == "__main__":
    unittest.main()
