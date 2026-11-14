
import unittest
from decimal import Decimal

from app.pricing import calculate_fare


class CalculateFareTests(unittest.TestCase):

    def calculate(
        self,
        *,
        base=5000,
        per_km=0,
        per_minute=0,
        distance="0",
        duration="0",
        anonymous=False,
        minimum=None,
        maximum=None,
    ):
        return calculate_fare(
            base_price_kopecks=base,
            price_per_km_kopecks=per_km,
            price_per_minute_kopecks=per_minute,
            distance_km=Decimal(distance),
            duration_minutes=Decimal(duration),
            anonymous=anonymous,
            minimum_fare_kopecks=minimum,
            maximum_fare_kopecks=maximum,
        )

    def test_base_price_only(self):
        result = self.calculate()
        self.assertEqual(result.total_price_kopecks, 5000)

    def test_distance_and_time(self):
        result = self.calculate(
            base=5000,
            per_km=2000,
            per_minute=100,
            distance="3",
            duration="10",
        )

        self.assertEqual(result.distance_price_kopecks, 6000)
        self.assertEqual(result.time_price_kopecks, 1000)
        self.assertEqual(result.total_price_kopecks, 12000)

    def test_anonymous_surcharge(self):
        result = self.calculate(anonymous=True)

        self.assertEqual(
            result.anonymous_surcharge_kopecks,
            10000,
        )
        self.assertEqual(result.total_price_kopecks, 15000)

    def test_minimum_fare_is_applied(self):
        result = self.calculate(
            base=10000,
            minimum=20000,
        )

        self.assertEqual(
            result.fare_limit_adjustment_kopecks,
            10000,
        )
        self.assertEqual(result.total_price_kopecks, 20000)

    def test_maximum_fare_is_applied(self):
        result = self.calculate(
            base=150000,
            maximum=100000,
        )

        self.assertEqual(
            result.fare_limit_adjustment_kopecks,
            -50000,
        )
        self.assertEqual(result.total_price_kopecks, 100000)

    def test_anonymous_surcharge_is_added_after_maximum(self):
        result = self.calculate(
            base=150000,
            maximum=100000,
            anonymous=True,
        )

        self.assertEqual(
            result.anonymous_surcharge_kopecks,
            10000,
        )
        self.assertEqual(result.total_price_kopecks, 110000)

    def test_anonymous_surcharge_is_added_after_minimum(self):
        result = self.calculate(
            base=10000,
            minimum=20000,
            anonymous=True,
        )

        self.assertEqual(result.total_price_kopecks, 30000)

    def test_fare_inside_limits_is_not_changed(self):
        result = self.calculate(
            base=50000,
            minimum=20000,
            maximum=100000,
        )

        self.assertEqual(
            result.fare_limit_adjustment_kopecks,
            0,
        )
        self.assertEqual(result.total_price_kopecks, 50000)

    def test_minimum_equal_to_maximum_is_allowed(self):
        result = self.calculate(
            base=50000,
            minimum=30000,
            maximum=30000,
        )

        self.assertEqual(result.total_price_kopecks, 30000)

    def test_limits_can_be_omitted(self):
        result = self.calculate(
            base=50000,
            minimum=None,
            maximum=None,
        )

        self.assertEqual(result.total_price_kopecks, 50000)

    def test_fractional_distance_rounding(self):
        result = self.calculate(
            base=0,
            per_km=1000,
            distance="1.25",
        )

        self.assertEqual(result.distance_price_kopecks, 1250)

    def test_fractional_time_rounding(self):
        result = self.calculate(
            base=0,
            per_minute=100,
            duration="2.5",
        )

        self.assertEqual(result.time_price_kopecks, 250)

    def test_half_kopeck_rounds_up(self):
        result = self.calculate(
            base=0,
            per_km=1,
            distance="0.5",
        )

        self.assertEqual(result.distance_price_kopecks, 1)

    def test_negative_distance_is_rejected(self):
        with self.assertRaises(ValueError):
            self.calculate(distance="-1")

    def test_negative_time_is_rejected(self):
        with self.assertRaises(ValueError):
            self.calculate(duration="-1")

    def test_negative_tariff_prices_are_rejected(self):
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
                    self.calculate(
                        base=base,
                        per_km=per_km,
                        per_minute=per_minute,
                    )

    def test_negative_minimum_is_rejected(self):
        with self.assertRaises(ValueError):
            self.calculate(minimum=-1)

    def test_negative_maximum_is_rejected(self):
        with self.assertRaises(ValueError):
            self.calculate(maximum=-1)

    def test_maximum_below_minimum_is_rejected(self):
        with self.assertRaises(ValueError):
            self.calculate(
                minimum=20000,
                maximum=10000,
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
