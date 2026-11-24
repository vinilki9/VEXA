"""Static Android wiring checks for VEXA 0.3.19; not a substitute for Android APK tests."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'android/shared/vexa-map-offline/src/main/java/ru/vexa/offline'
CLIENT = ROOT / 'android/client/app/src/main/java/ru/vexa/client/VexaMapView.kt'
DRIVER = ROOT / 'android/driver/app/src/main/java/ru/vexa/driver/DriverMap.kt'

class MapCameraAndVectorContracts(unittest.TestCase):
    def test_passenger_is_fixed_north_up_and_flat(self):
        client = CLIENT.read_text()
        for pattern in ('isTiltGesturesEnabled = false', 'isRotateGesturesEnabled = false',
                        'setMaxPitchPreference(0.0)', 'PASSENGER_TILT', 'PASSENGER_BEARING',
                        'buildings3d = false', '.tilt(0.0).bearing(0.0)'):
            self.assertIn(pattern, client)
        self.assertNotIn('DriverMapPerspective', client)
        self.assertNotIn('view=3d', client)

    def test_driver_can_toggle_and_persist_perspective(self):
        driver = DRIVER.read_text()
        for marker in ('DriverMapPerspective', 'DriverMapPreference.load',
                       'DriverMapPreference.save', 'perspective.next()',
                       'Навигация: ${perspective.label}', 'setMaxPitchPreference(if (threeD) 60.0 else 0.0)',
                       '?view=3d', 'buildings3d = perspective == DriverMapPerspective.THREE_D',
                       'followDriver = !followDriver', 'location?.let { DriverPoint'):
            self.assertIn(marker, driver)

    def test_local_renderer_vector_tiles_and_local_glyphs_only(self):
        source = (COMMON / 'OfflineMbtilesServer.kt').read_text()
        for marker in ('/vector/', '/glyphs/', 'vectorStyleJson', 'vexa_glyphs',
                       'Noto Sans Regular', 'Content-Encoding: gzip',
                       'transportation_name', 'fill-extrusion', 'isGzip(',
                       'ServerSocket(0, 16, InetAddress.getByName("127.0.0.1"))'):
            self.assertIn(marker, source)
        self.assertNotIn('fonts.googleapis', source)

    def test_same_version_and_shared_module_both_apps(self):
        for app in ('client', 'driver'):
            gradle = (ROOT/f'android/{app}/app/build.gradle.kts').read_text()
            self.assertIn('versionCode = 19', gradle)
            self.assertIn('versionName = "0.3.19"', gradle)
            self.assertIn('implementation(project(":vexa-map-offline"))', gradle)

    def test_driver_maneuvers_are_not_misrepresented_as_voice_navigation(self):
        server = (ROOT/'VEXA_MAP/server/vexa_map_server.py').read_text()
        self.assertIn('steps=true', server)
        self.assertIn('"maneuvers": maneuvers', server)
        documentation = (ROOT/'VEXA_MAP/VECTOR_2D_3D_0.3.19.md').read_text()
        self.assertIn('not yet production ready', documentation)
        self.assertIn('No real vector/imagery/road/font data', documentation)

if __name__ == '__main__':
    unittest.main()
