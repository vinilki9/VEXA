import copy
import unittest

from app.price_breakdown import PriceBreakdownError, build_price_breakdown


class PriceBreakdownTests(unittest.TestCase):
    def quote(self):
        return {
            "fare_base_price_kopecks": 15000,
            "fare_distance_price_kopecks": 6500,
            "fare_time_price_kopecks": 2500,
            "fare_limit_adjustment_kopecks": 0,
            "dynamic_pricing_multiplier": "1.25",
            "fare_dynamic_adjustment_kopecks": 6000,
            "child_seat_surcharge_kopecks": 10000,
            "animal_transport_surcharge_kopecks": 0,
            "cargo_vehicle_surcharge_kopecks": 0,
            "cargo_loaders_surcharge_kopecks": 0,
            "price_kopecks": 40000,
            "price_rub": 400,
        }

    def test_transparent_components_match_total(self):
        result = build_price_breakdown(self.quote())
        self.assertEqual(result["trip_subtotal_kopecks"], 24000)
        self.assertEqual(result["total_kopecks"], 40000)
        self.assertEqual(sum(item["amount_kopecks"] for item in result["lines"]), 40000)
        self.assertIn("child_seat", [item["code"] for item in result["lines"]])
        self.assertNotIn("animals", [item["code"] for item in result["lines"]])

    def test_rounding_with_half_kopeck(self):
        q = self.quote()
        q.update(
            fare_base_price_kopecks=3,
            fare_distance_price_kopecks=0,
            fare_time_price_kopecks=0,
            fare_dynamic_adjustment_kopecks=2,
            child_seat_surcharge_kopecks=0,
            dynamic_pricing_multiplier="1.5",
            price_kopecks=5,
            price_rub=0,
        )
        self.assertEqual(build_price_breakdown(q)["total_kopecks"], 5)

    def test_total_mismatch(self):
        q = self.quote()
        q["price_kopecks"] += 1
        with self.assertRaises(PriceBreakdownError):
            build_price_breakdown(q)

    def test_wrong_dynamic_adjustment(self):
        q = self.quote()
        q["fare_dynamic_adjustment_kopecks"] += 1
        q["price_kopecks"] += 1
        with self.assertRaises(PriceBreakdownError):
            build_price_breakdown(q)

    def test_wrong_rounded_rubles(self):
        q = self.quote()
        q["price_rub"] += 1
        with self.assertRaises(PriceBreakdownError):
            build_price_breakdown(q)

    def test_rejects_negative_surcharge(self):
        q = self.quote()
        q["child_seat_surcharge_kopecks"] = -100
        with self.assertRaises(PriceBreakdownError):
            build_price_breakdown(q)

    def test_rejects_bool_as_money(self):
        q = self.quote()
        q["fare_time_price_kopecks"] = True
        with self.assertRaises(PriceBreakdownError):
            build_price_breakdown(q)

    def test_rejects_nonfinite_multiplier(self):
        for multiplier in ("NaN", "Infinity", "0.5"):
            with self.subTest(multiplier=multiplier):
                q = self.quote()
                q["dynamic_pricing_multiplier"] = multiplier
                with self.assertRaises(PriceBreakdownError):
                    build_price_breakdown(q)

    def test_negative_fare_limit_adjustment_is_valid(self):
        q = self.quote()
        q["fare_limit_adjustment_kopecks"] = -4000
        q["fare_dynamic_adjustment_kopecks"] = 5000
        q["price_kopecks"] = 35000
        q["price_rub"] = 350
        self.assertEqual(build_price_breakdown(q)["trip_subtotal_kopecks"], 20000)


if __name__ == "__main__":
    unittest.main()
