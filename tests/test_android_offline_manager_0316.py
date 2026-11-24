"""Static contracts for the shared Android offline download manager.
Does NOT replace Android compilation or live network/device testing.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'android/shared/vexa-map-offline'
SOURCES = COMMON / 'src/main/java/ru/vexa/offline'


class OfflineAndroidContracts(unittest.TestCase):
    def test_single_shared_android_module(self):
        self.assertTrue((COMMON / 'build.gradle.kts').is_file())
        self.assertTrue((SOURCES / 'OfflineMapRules.kt').is_file())
        self.assertTrue((SOURCES / 'OfflineMapsRepository.kt').is_file())
        self.assertTrue((SOURCES / 'OfflineMapsScreen.kt').is_file())

    def test_both_apps_use_shared_module(self):
        for name in ('client', 'driver'):
            with self.subTest(app=name):
                settings = (ROOT / f'android/{name}/settings.gradle.kts').read_text()
                gradle = (ROOT / f'android/{name}/app/build.gradle.kts').read_text()
                self.assertIn('include(":app", ":vexa-map-offline")', settings)
                self.assertIn('file("../shared/vexa-map-offline")', settings)
                self.assertIn('implementation(project(":vexa-map-offline"))', gradle)
                self.assertIn('VEXA_MAP_BASE_URL', gradle)

    def test_settings_link_to_manager(self):
        paths = [
            ROOT/'android/client/app/src/main/java/ru/vexa/client/VexaClientSettingsScreen.kt',
            ROOT/'android/driver/app/src/main/java/ru/vexa/driver/DriverSettingsScreen.kt',
        ]
        for path in paths:
            with self.subTest(path=path.name):
                text = path.read_text()
                self.assertIn('OfflineMapsScreen(', text)
                self.assertIn('offlineMapsOpen = true', text)
                self.assertIn('allowDebugHttp = BuildConfig.DEBUG', text)
                self.assertIn('BackHandler { offlineMapsOpen = false }', text)

    def test_six_safety_properties_present(self):
        repo = (SOURCES / 'OfflineMapsRepository.kt').read_text()
        for expected in (
            'root.usableSpace',
            'followRedirects(false)',
            'If-Range',
            'Content-Range',
            'MessageDigest.getInstance("SHA-256")',
            'StandardCopyOption.ATOMIC_MOVE',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, repo)

    def test_catalog_districts_and_navigation_capability_disclosure(self):
        rules = (SOURCES / 'OfflineMapRules.kt').read_text()
        screen = (SOURCES / 'OfflineMapsScreen.kt').read_text()
        self.assertEqual(rules.count(' to "') - 0, 8)
        self.assertIn('PNG/JPEG/WebP', screen)
        self.assertIn('навигационного индекса VEXA v1', screen)
        self.assertIn('не учитывают повороты', screen)

    def test_server_protocol_is_same(self):
        server = (ROOT/'VEXA_MAP/server/vexa_map_server.py').read_text()
        repo = (SOURCES/'OfflineMapsRepository.kt').read_text()
        for route in ('/v1/offline/catalog', '/v1/offline/regions/'):
            self.assertIn(route, repo)
            self.assertIn(route, server)


if __name__ == '__main__':
    unittest.main()
