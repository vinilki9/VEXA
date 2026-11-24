"""Source-level contracts for UX phase 1. NOT a substitute for Gradle/E2E tests."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / 'android/client/app/src/main/java/ru/vexa/client'
DRIVER = ROOT / 'android/driver/app/src/main/java/ru/vexa/driver'
BACKEND = ROOT / 'backend/app'

class UXContracts(unittest.TestCase):
    def read(self, path):
        return path.read_text(encoding='utf-8')

    def test_client_home_work_scoped_to_account(self):
        s = self.read(CLIENT/'VexaSavedPlaces.kt')
        self.assertIn('getPassengerPhone()', s)
        self.assertIn('getAccessToken()', s)
        self.assertIn('SHA-256', s)
        self.assertIn('clearCurrentAccount', s)
        self.assertIn('MODE_PRIVATE', s)

    def test_client_has_usable_shortcuts(self):
        s = self.read(CLIENT/'MainActivity.kt')
        self.assertIn('VexaClientQuickDestinations(', s)
        self.assertIn('VexaSavedPlaces.save', s)
        self.assertIn('savedPlaceMessage', s)
        self.assertIn('settingsRevision', s)

    def test_pickup_instructions_reach_backend_and_driver(self):
        p = self.read(CLIENT/'PassengerOrderRepository.kt')
        self.assertEqual(p.count('pickupComment = pickupComment'), 2)
        self.assertIn('put("comment",', p)
        self.assertIn('pickupComment.length <= 500', p)
        b = self.read(BACKEND/'driver_api.py')
        self.assertIn('"comment": order.comment,', b)
        d = self.read(DRIVER/'MainActivity.kt')
        self.assertIn('order.optString("comment")', d)

    def test_ride_share_is_explicit_without_tracking_link(self):
        s = self.read(CLIENT/'VexaRideShare.kt')
        self.assertIn('Intent.ACTION_SEND', s)
        self.assertIn('Intent.createChooser', s)
        self.assertNotIn('Authorization', s)
        self.assertIn('не ссылка для отслеживания', s)

    def test_driver_first_screen_prioritizes_offer_and_map(self):
        s = self.read(DRIVER/'MainActivity.kt')
        self.assertLess(s.index('if (currentOffer != null && online) {\n      item {'),
                        s.index('DriverHomeMapCard('))
        self.assertLess(s.index('DriverHomeMapCard('),
                        s.index('text = "Финансы",'))

    def test_driver_break_is_real_offline_request_and_guarded(self):
        s = self.read(DRIVER/'MainActivity.kt')
        self.assertIn('changeOnlineStatus(false, startBreak = true)',s)
        self.assertIn('DriverDutyRules.canStartBreak(',s)
        self.assertIn('DriverLocationService.stop(context)',s)
        self.assertIn('setOnline(value)', s)
        self.assertIn('!online || canBreak', s)

    def test_no_new_gis_dependency(self):
        for app in ('client','driver'):
            gradle = self.read(ROOT/f'android/{app}/app/build.gradle.kts')
            self.assertIn('org.maplibre.gl:android-sdk',gradle)
            self.assertNotIn('ru.dgis.sdk',gradle)

if __name__=='__main__': unittest.main()
