"""Source/API contracts for the 0.3.8 additions; NOT Android runtime tests."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "android/client/app/src/main/java/ru/vexa/client"
DRIVER = ROOT / "android/driver/app/src/main/java/ru/vexa/driver"


class AdditionalFeaturesContracts(unittest.TestCase):
    def test_history_endpoint_requires_authenticated_passenger(self):
        backend = (ROOT / "backend/app/main.py").read_text()
        self.assertIn('"/api/v1/passenger/orders"', backend)
        self.assertIn("passenger: User = Depends(get_current_passenger)", backend)
        self.assertIn("Order.passenger_user_id == passenger.id", backend)

    def test_mobile_history_uses_existing_authenticated_api(self):
        api = (CLIENT / "ApiClient.kt").read_text()
        self.assertIn('suspend fun getPassengerOrders()', api)
        self.assertIn('header("Authorization", "Bearer $token")', api)
        history = (CLIENT / "VexaTripHistoryDialog.kt").read_text()
        self.assertIn("JSONArray(ApiClient.getPassengerOrders())", history)

    def test_history_handles_auth_and_network_error(self):
        history = (CLIENT / "VexaTripHistoryDialog.kt").read_text()
        self.assertIn('error.statusCode == 401', history)
        self.assertIn('error.statusCode == 403', history)
        self.assertIn('"Обновить"', history)
        self.assertIn('orders = emptyList()', history)

    def test_repeat_trip_uses_validated_coordinates_and_never_creates_order(self):
        history = (CLIENT / "VexaTripHistoryDialog.kt").read_text()
        activity = (CLIENT / "MainActivity.kt").read_text()
        self.assertIn('lat in -90.0..90.0', history)
        self.assertIn('lon in -180.0..180.0', history)
        self.assertIn('onRepeatTrip(pickup, destination)', history)
        self.assertNotIn('PassengerOrderRepository.createOrder(', history)
        self.assertIn('pricePreview = null', activity)
        self.assertIn('pricePreviewSignature = null', activity)
        self.assertIn('orderCreated && !orderTerminal', activity)

    def test_current_order_allows_new_trip_only_when_terminal(self):
        status = (CLIENT / "PassengerOrderStatusPanel.kt").read_text()
        self.assertIn('status == "completed" || status == "cancelled"', status)
        self.assertIn('Text("Новая поездка")', status)
        self.assertIn('onTerminal()', status)

    def test_driver_order_response_exposes_real_coordinates_and_phone(self):
        api = (ROOT / "backend/app/driver_api.py").read_text()
        self.assertIn('"customer_phone": order.customer_phone', api)
        self.assertIn('"latitude": order.pickup_latitude', api)
        self.assertIn('"latitude": order.destination_latitude', api)

    def test_driver_navigation_checks_coordinates_and_external_app(self):
        actions = (DRIVER / "DriverQuickActions.kt").read_text()
        main = (DRIVER / "MainActivity.kt").read_text()
        self.assertIn('lat in -90.0..90.0', actions)
        self.assertIn('lon in -180.0..180.0', actions)
        self.assertIn('Intent(Intent.ACTION_VIEW', actions)
        self.assertIn('DriverQuickActions.openNavigator(context, pickupPoint)', main)
        self.assertIn('DriverQuickActions.openNavigator(context, destinationPoint)', main)
        self.assertIn('внешнем приложении', main)

    def test_phone_uses_dialer_not_direct_call_permission(self):
        actions = (DRIVER / "DriverQuickActions.kt").read_text()
        manifest = (ROOT / "android/driver/app/src/main/AndroidManifest.xml").read_text()
        self.assertIn('Intent.ACTION_DIAL', actions)
        self.assertNotIn('Intent.ACTION_CALL', actions)
        self.assertNotIn('android.permission.CALL_PHONE', manifest)
        self.assertIn('validPhone(phone)', actions)

    def test_version_bumped_both_apps(self):
        for app in ("client", "driver"):
            build = (ROOT / f"android/{app}/app/build.gradle.kts").read_text()
            # Version 0.3.8 introduced the feature; later versions must retain it.
            code = re.search(r'versionCode\s*=\s*(\d+)', build)
            self.assertIsNotNone(code)
            self.assertGreaterEqual(int(code.group(1)), 8)
            self.assertRegex(build, r'versionName\s*=\s*"0\.3\.\d+"')


if __name__ == "__main__":
    unittest.main()
