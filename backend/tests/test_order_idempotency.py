
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError
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


class OrderIdempotencyTests(unittest.TestCase):
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

    @patch("app.main.calculate_order_route_price")
    def test_repeated_key_returns_existing_order_without_recalculation(
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

        first_response = create_order(
            payload=self.payload,
            idempotency_key="vexa-test-order-001",
            db=self.db,
        )

        second_response = create_order(
            payload=self.payload,
            idempotency_key="vexa-test-order-001",
            db=self.db,
        )

        order_count = self.db.scalar(
            select(func.count()).select_from(Order)
        )

        self.assertEqual(
            first_response["id"],
            second_response["id"],
        )
        self.assertEqual(order_count, 1)

        self.assertEqual(
            second_response["route_distance_meters"],
            2500,
        )
        self.assertEqual(
            second_response["route_duration_seconds"],
            600,
        )
        self.assertEqual(
            second_response["routing_provider"],
            "osrm",
        )
        self.assertEqual(
            second_response["price_kopecks"],
            21000,
        )

        calculate_route.assert_called_once()

    @patch("app.main.calculate_order_route_price")
    def test_different_keys_create_separate_orders(
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

        first_response = create_order(
            payload=self.payload,
            idempotency_key="vexa-test-order-002",
            db=self.db,
        )

        second_response = create_order(
            payload=self.payload,
            idempotency_key="vexa-test-order-003",
            db=self.db,
        )

        order_count = self.db.scalar(
            select(func.count()).select_from(Order)
        )

        self.assertNotEqual(
            first_response["id"],
            second_response["id"],
        )
        self.assertEqual(order_count, 2)

        self.assertEqual(
            first_response["price_kopecks"],
            21000,
        )
        self.assertEqual(
            second_response["price_kopecks"],
            21000,
        )

        calculate_route.assert_called()
        self.assertEqual(calculate_route.call_count, 2)

    @patch("app.main.calculate_order_route_price")
    def test_database_rejects_duplicate_idempotency_key(
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
            idempotency_key="vexa-race-test-001",
            db=self.db,
        )

        original = self.db.scalar(
            select(Order).where(
                Order.city_id == self.city.id,
                Order.idempotency_key == "vexa-race-test-001",
            )
        )

        duplicate_data = {
            column.key: getattr(original, column.key)
            for column in Order.__table__.columns
            if column.key not in ("id", "created_at", "updated_at")
        }
        duplicate_data["public_number"] = "VEXA-OB-DUPLICATE"

        duplicate = Order(**duplicate_data)
        self.db.add(duplicate)

        with self.assertRaises(IntegrityError) as context:
            self.db.commit()

        self.assertIn(
            "idempotency_key",
            str(context.exception),
        )

        self.db.rollback()

        order_count = self.db.scalar(
            select(func.count()).select_from(Order)
        )
        self.assertEqual(order_count, 1)


if __name__ == "__main__":
    unittest.main()
