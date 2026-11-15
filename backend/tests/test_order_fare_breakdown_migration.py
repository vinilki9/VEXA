
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sqlalchemy import CheckConstraint

from app.models import Order


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0005_add_order_fare_breakdown.py"
)

SPEC = importlib.util.spec_from_file_location(
    "vexa_migration_0005",
    MIGRATION_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load migration 0005")

MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


FARE_FIELDS = (
    "fare_base_price_kopecks",
    "fare_distance_price_kopecks",
    "fare_time_price_kopecks",
    "fare_limit_adjustment_kopecks",
    "anonymous_surcharge_kopecks",
)


class OrderFareBreakdownMigrationTests(unittest.TestCase):

    def test_revision_chain(self):
        self.assertEqual(
            MIGRATION.revision,
            "0005_add_order_fare_breakdown",
        )
        self.assertEqual(
            MIGRATION.down_revision,
            "0004_add_tariff_change_history",
        )

    def test_upgrade_adds_all_fare_fields(self):
        operations = Mock()

        with patch.object(MIGRATION, "op", operations):
            MIGRATION.upgrade()

        self.assertEqual(
            operations.add_column.call_count,
            len(FARE_FIELDS),
        )

        added_fields = [
            call.args[1].name
            for call in operations.add_column.call_args_list
        ]

        self.assertEqual(
            set(added_fields),
            set(FARE_FIELDS),
        )

        for call in operations.add_column.call_args_list:
            self.assertTrue(call.args[1].nullable)

    def test_upgrade_creates_consistency_constraint(self):
        operations = Mock()

        with patch.object(MIGRATION, "op", operations):
            MIGRATION.upgrade()

        operations.create_check_constraint.assert_called_once()

        call = operations.create_check_constraint.call_args
        constraint_name = call.args[0]
        table_name = call.args[1]
        expression = " ".join(call.args[2].split()).lower()

        self.assertEqual(
            constraint_name,
            "orders_fare_breakdown_consistent",
        )
        self.assertEqual(table_name, "orders")

        self.assertIn("price_kopecks is not null", expression)

        for field in FARE_FIELDS:
            self.assertIn(field, expression)

        self.assertIn("price_kopecks =", expression)

    def test_downgrade_removes_constraint_and_all_fields(self):
        operations = Mock()

        with patch.object(MIGRATION, "op", operations):
            MIGRATION.downgrade()

        operations.drop_constraint.assert_called_once_with(
            "orders_fare_breakdown_consistent",
            "orders",
            type_="check",
        )

        self.assertEqual(
            operations.drop_column.call_count,
            len(FARE_FIELDS),
        )

        removed_fields = [
            call.args[1]
            for call in operations.drop_column.call_args_list
        ]

        self.assertEqual(
            set(removed_fields),
            set(FARE_FIELDS),
        )

    def test_model_contains_matching_constraint(self):
        constraint = next(
            (
                item
                for item in Order.__table__.constraints
                if isinstance(item, CheckConstraint)
                and item.name == "orders_fare_breakdown_consistent"
            ),
            None,
        )

        self.assertIsNotNone(constraint)

        expression = " ".join(
            str(constraint.sqltext).split()
        ).lower()

        self.assertIn("price_kopecks is not null", expression)

        for field in FARE_FIELDS:
            self.assertIn(field, expression)

        self.assertIn("price_kopecks =", expression)


if __name__ == "__main__":
    unittest.main()
