
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.main import order_to_response
from app.schemas import OrderResponse


class OrderResponseSerializationTests(unittest.TestCase):
    def make_order(self, **overrides):
        data = {
            "id": uuid4(),
            "public_number": "VEXA-OB-000125",
            "city_id": uuid4(),
            "tariff_id": uuid4(),
            "branch_id": uuid4(),
            "passenger_user_id": None,
            "driver_user_id": None,
            "vehicle_id": None,
            "customer_name": "Иван",
            "customer_phone": "+79990000000",
            "pickup_address": "Оболенск, улица Ленина, 1",
            "destination_address": "Оболенск, улица Центральная, 5",
            "pickup_latitude": 54.9,
            "pickup_longitude": 37.2,
            "destination_latitude": 54.91,
            "destination_longitude": 37.21,
            "route_distance_meters": 2500,
            "route_duration_seconds": 600,
            "routing_provider": "osrm",
            "status": "new",
            "payment_method": "cash",
            "price_rub": 210,
            "price_kopecks": 21000,
            "comment": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        data.update(overrides)
        return SimpleNamespace(**data)

    def test_route_metadata_is_preserved_in_json_response(self):
        order = self.make_order()
        city = SimpleNamespace(
            id=order.city_id,
            code="obolensk",
        )

        payload = order_to_response(order, city)
        response = OrderResponse.model_validate(payload)
        result = json.loads(response.model_dump_json())

        self.assertEqual(result["route_distance_meters"], 2500)
        self.assertEqual(result["route_duration_seconds"], 600)
        self.assertEqual(result["routing_provider"], "osrm")
        self.assertEqual(result["public_number"], "VEXA-OB-000125")
        self.assertEqual(result["price_kopecks"], 21000)
        self.assertEqual(result["customer_name"], "Иван")

    def test_missing_route_metadata_is_serialized_as_null(self):
        order = self.make_order(
            route_distance_meters=None,
            route_duration_seconds=None,
            routing_provider=None,
        )
        city = SimpleNamespace(
            id=order.city_id,
            code="obolensk",
        )

        payload = order_to_response(order, city)
        response = OrderResponse.model_validate(payload)
        result = json.loads(response.model_dump_json())

        self.assertIsNone(result["route_distance_meters"])
        self.assertIsNone(result["route_duration_seconds"])
        self.assertIsNone(result["routing_provider"])


if __name__ == "__main__":
    unittest.main()
