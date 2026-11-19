
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0014_remove_anonymous_order.py"
)

SPEC = importlib.util.spec_from_file_location(
    "vexa_migration_0014",
    MIGRATION_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load migration 0014")

MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


class RemoveAnonymousOrderMigrationTests(unittest.TestCase):

    def test_revision_chain(self):
        self.assertEqual(
            MIGRATION.revision,
            "0014_remove_anonymous_order",
        )
        self.assertEqual(
            MIGRATION.down_revision,
            "0013_merge_migration_heads",
        )

    def test_upgrade_backfills_missing_names(self):
        operations = Mock()

        with patch.object(MIGRATION, "op", operations):
            MIGRATION.upgrade()

        sql = operations.execute.call_args.args[0]

        self.assertIn("UPDATE orders", sql)
        self.assertIn("customer_name = 'Не указано'", sql)
        self.assertIn("customer_name IS NULL", sql)
        self.assertIn("BTRIM(customer_name)", sql)

    def test_upgrade_removes_anonymous_columns(self):
        operations = Mock()

        with patch.object(MIGRATION, "op", operations):
            MIGRATION.upgrade()

        removed = {
            call.args[1]
            for call in operations.drop_column.call_args_list
        }

        self.assertEqual(
            removed,
            {
                "anonymous",
                "anonymous_surcharge_kopecks",
            },
        )

    def test_upgrade_requires_customer_name(self):
        operations = Mock()

        with patch.object(MIGRATION, "op", operations):
            MIGRATION.upgrade()

        operations.alter_column.assert_called_once()

        args = operations.alter_column.call_args
        self.assertEqual(args.args[0], "orders")
        self.assertEqual(args.args[1], "customer_name")
        self.assertFalse(args.kwargs["nullable"])

    def test_upgrade_recreates_fare_constraint(self):
        operations = Mock()

        with patch.object(MIGRATION, "op", operations):
            MIGRATION.upgrade()

        operations.drop_constraint.assert_called_once_with(
            "orders_fare_breakdown_consistent",
            "orders",
            type_="check",
        )

        operations.create_check_constraint.assert_called_once()

        call = operations.create_check_constraint.call_args
        expression = " ".join(call.args[2].split()).lower()

        self.assertEqual(
            call.args[0],
            "orders_fare_breakdown_consistent",
        )
        self.assertNotIn("anonymous", expression)
        self.assertIn("child_seat_surcharge_kopecks", expression)
        self.assertIn("animal_transport_surcharge_kopecks", expression)
        self.assertIn("price_kopecks =", expression)

    def test_downgrade_restores_legacy_columns(self):
        operations = Mock()

        with patch.object(MIGRATION, "op", operations):
            MIGRATION.downgrade()

        added = {
            call.args[1].name
            for call in operations.add_column.call_args_list
        }

        self.assertEqual(
            added,
            {
                "anonymous",
                "anonymous_surcharge_kopecks",
            },
        )

        operations.alter_column.assert_called_once()

        self.assertEqual(
            operations.create_check_constraint.call_count,
            1,
        )


if __name__ == "__main__":
    unittest.main()
