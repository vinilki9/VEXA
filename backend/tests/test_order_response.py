
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.schemas import OrderResponse


class OrderResponseSerializationTests(unittest.TestCase):
    def make_order(self, **overrides):
        data = {
            "id": uuid4(),
            "public_number": "VEXA-OB-000125",
            "city_id": uuid4(),
            "city_code": "obolensk",
            "customer_phone": "+79990000000",
            "anonymous": False,
            "pickup_address": "Оболенск, улица Ленина, 1",
            "destination_address": "Оболенск, улица Центральная, 5",
            "status": "new",
            "payment_method": "cash",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "route_distance_meters": 2500,
            "route_duration_seconds": 600,
            "routing_provider": "osrm",
        }
        data.update(overrides)
        return SimpleNamespace(**data)

    def test_route_metadata_is_preserved_in_json_response(self):
        order = self.make_order()

        response = OrderResponse.model_validate(order)
        result = json.loads(response.model_dump_json())

        self.assertEqual(result["route_distance_meters"], 2500)
        self.assertEqual(result["route_duration_seconds"], 600)
        self.assertEqual(result["routing_provider"], "osrm")
        self.assertEqual(result["public_number"], "VEXA-OB-000125")

    def test_missing_route_metadata_is_serialized_as_null(self):
        order = self.make_order(
            route_distance_meters=None,
            route_duration_seconds=None,
            routing_provider=None,
        )

        response = OrderResponse.model_validate(order)
        result = json.loads(response.model_dump_json())

        self.assertIsNone(result["route_distance_meters"])
        self.assertIsNone(result["route_duration_seconds"])
        self.assertIsNone(result["routing_provider"])


if __name__ == "__main__":
    unittest.main()
