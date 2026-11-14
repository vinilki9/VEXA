
import unittest

from unittest.mock import patch
from decimal import Decimal
from pydantic import ValidationError
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import create_order
from app.models import (
    Branch,
    City,
    CityOrderCounter,
    Order,
    Tariff,
)
from app.schemas import OrderCreate
from app.routing import RouteResult

class OrderValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(
            bind=cls.engine,
            autoflush=False,
            autocommit=False,
        )

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(cls.engine)
        cls.engine.dispose()

    def setUp(self):
        self.db = self.Session()

        self.db.execute(delete(Order))
        self.db.execute(delete(CityOrderCounter))
        self.db.execute(delete(Tariff))
        self.db.execute(delete(Branch))
        self.db.execute(delete(City))
        self.db.commit()

        self.city = City(
            code="obolensk",
            name="Оболенск",
            is_active=True,
        )
        self.db.add(self.city)
        self.db.flush()

        self.branch = Branch(
            city_id=self.city.id,
            name="Главный филиал",
            is_active=True,
        )
        self.db.add(self.branch)

        self.tariff = Tariff(
            city_id=self.city.id,
            code="standard",
            name="Стандарт",
            vehicle_class="standard",
            base_price_kopecks=5000,
            price_per_km_kopecks=2000,
            price_per_minute_kopecks=100,
            is_active=True,
        )
        self.db.add(self.tariff)
        self.db.commit()

        self.payload = OrderCreate(
            city_code="obolensk",
            tariff_id=self.tariff.id,
            customer_name="Иван",
            customer_phone="+79990000000",
            pickup_address="Оболенск, улица Ленина, 1",
            destination_address="Оболенск, улица Центральная, 5",
            pickup_latitude=54.9,
            pickup_longitude=37.2,
            destination_latitude=54.91,
            destination_longitude=37.21,
            payment_method="cash",
        )

    def tearDown(self):
        self.db.close()

    def assert_order_rejected(self, payload, expected_status):
        with patch(
            "app.main.calculate_order_route_price"
        ) as calculate_route:
            with self.assertRaises(HTTPException) as context:
                create_order(
                    payload=payload,
                    idempotency_key="vexa-validation-test",
                    db=self.db,
                )

            self.assertEqual(
                context.exception.status_code,
                expected_status,
            )
            calculate_route.assert_not_called()

    def test_inactive_city_is_rejected(self):
        self.city.is_active = False
        self.db.commit()

        self.assert_order_rejected(self.payload, 400)

    def test_missing_tariff_is_rejected(self):
        payload = self.payload.model_copy(
            update={"tariff_id": None}
        )

        self.assert_order_rejected(payload, 400)

    def test_inactive_tariff_is_rejected(self):
        self.tariff.is_active = False
        self.db.commit()

        self.assert_order_rejected(self.payload, 400)

    def test_missing_active_branch_is_rejected(self):
        self.db.delete(self.branch)
        self.db.commit()

        self.assert_order_rejected(self.payload, 503)

    def test_multiple_active_branches_are_rejected(self):
        second_branch = Branch(
            city_id=self.city.id,
            name="Второй филиал",
            is_active=True,
        )
        self.db.add(second_branch)
        self.db.commit()
        self.assert_order_rejected(self.payload, 409)


    def test_missing_pickup_coordinates_are_rejected(self):
        payload = self.payload.model_copy(
            update={
                "pickup_latitude": None,
            }
        )

        self.assert_order_rejected(payload, 400)

    def test_missing_destination_coordinates_are_rejected(self):
        payload = self.payload.model_copy(
            update={
                "destination_longitude": None,
            }
        )

        self.assert_order_rejected(payload, 400)

    def test_out_of_range_coordinates_are_rejected(self):
        invalid_values = [
            ("pickup_latitude", 91),
            ("pickup_latitude", -91),
            ("pickup_longitude", 181),
            ("destination_longitude", -181),
        ]

        for field, value in invalid_values:
            with self.subTest(field=field, value=value):
                payload_data = self.payload.model_dump()
                payload_data[field] = value

                with self.assertRaises(ValidationError):
                    OrderCreate.model_validate(payload_data)

    @patch("app.main.calculate_order_route_price")
    def test_valid_coordinates_are_passed_to_router(
        self,
        calculate_route,
    ):
        calculate_route.return_value = SimpleNamespace(
            route=RouteResult(
                distance_meters=Decimal("2500"),
                duration_seconds=Decimal("600"),
            ),
            fare=SimpleNamespace(
                total_price_kopecks=21000,
            ),
            provider_name="osrm",
        )

        create_order(
            payload=self.payload,
            idempotency_key="vexa-coordinates-test",
            db=self.db,
        )

        calculate_route.assert_called_once_with(
            pickup_latitude=54.9,
            pickup_longitude=37.2,
            destination_latitude=54.91,
            destination_longitude=37.21,
            base_price_kopecks=5000,
            price_per_km_kopecks=2000,
            price_per_minute_kopecks=100,
            anonymous=False,
        )

if __name__ == "__main__":
    unittest.main()
