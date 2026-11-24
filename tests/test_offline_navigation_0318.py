"""VEXA offline nav v1 wiring contracts; runtime must also be tested on Android."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SHARED=ROOT/'android/shared/vexa-map-offline/src/main/java/ru/vexa/offline'
class OfflineNavContracts(unittest.TestCase):
    def test_common_navigation_is_in_both_android_apps(self):
        self.assertTrue((SHARED/'OfflineNavigation.kt').is_file())
        for app in ('client','driver'):
            self.assertIn('implementation(project(":vexa-map-offline"))', (ROOT/f'android/{app}/app/build.gradle.kts').read_text())
            self.assertIn('versionCode = 19', (ROOT/f'android/{app}/app/build.gradle.kts').read_text())
    def test_client_uses_online_and_local_search_and_route(self):
        search=(ROOT/'android/client/app/src/main/java/ru/vexa/client/AddressSearch.kt').read_text()
        route=(ROOT/'android/client/app/src/main/java/ru/vexa/client/VexaRouting.kt').read_text()
        main=(ROOT/'android/client/app/src/main/java/ru/vexa/client/MainActivity.kt').read_text()
        for src in (search,route):
            self.assertIn('OfflineMapMode.load(context)',src)
            self.assertIn('OfflineMapMode.AUTO',src)
            self.assertIn('OfflineNavigation(context)',src)
        self.assertIn('VexaRouting.route(context, start, end)',main)
        self.assertIn('AddressSearch.search(context, query)',main)
        self.assertIn('OfflineMapMode.changeCounter.intValue',main)
        self.assertIn('не для расчёта тарифа',main)
    def test_driver_routes_locally_in_offline_mode(self):
        driver=(ROOT/'android/driver/app/src/main/java/ru/vexa/driver/DriverMap.kt').read_text()
        self.assertIn('OfflineNavigation(context).route(',driver)
        self.assertIn('if (offlineSelected)',driver)
        self.assertIn('fetchDriverRoute(pickup, destination)',driver)
        self.assertIn('не для расчёта тарифа',driver)
    def test_index_bounds_and_no_shortest_line_fallback(self):
        nav=(SHARED/'OfflineNavigation.kt').read_text()
        graph=(SHARED/'OfflineGraph.kt').read_text()
        for marker in ('60_000', '240_000', '90_000','vexa_terms','vexa_edges', 'SQLiteDatabase.OPEN_READONLY'):
            self.assertIn(marker,nav)
        for marker in ('PriorityQueue','e.seconds', 'maxSnapMeters','return null'):
            self.assertIn(marker,graph)
    def test_map_manager_shows_index_capabilities(self):
        screen=(SHARED/'OfflineMapsScreen.kt').read_text()
        for text in ('addressRegions', 'routeRegions', 'навигационного индекса VEXA v1'):
            self.assertIn(text,screen)
if __name__=='__main__':unittest.main()
