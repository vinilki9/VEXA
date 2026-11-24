"""Contracts: offline raster map renderer (not a replacement for Android device tests)."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / 'android/shared/vexa-map-offline/src/main/java/ru/vexa/offline'

class RasterOfflineContracts(unittest.TestCase):
    def test_shared_readonly_mbtiles_loader(self):
        text = (SHARED/'OfflineMbtilesServer.kt').read_text()
        for pattern in ('SQLiteDatabase.OPEN_READONLY', 'SELECT tile_data FROM tiles',
                        'OfflineTileMath.tmsRow', 'file.length()', 'filesDir',
                        'setOf("png", "jpg", "webp", "pbf")', 'localhost',):
            with self.subTest(pattern=pattern):
                if pattern == 'localhost':
                    self.assertIn('127.0.0.1', text)
                else: self.assertIn(pattern,text)
        self.assertNotIn('0.0.0.0', text)

    def test_only_local_loopback_listener(self):
        s = (SHARED/'OfflineMbtilesServer.kt').read_text()
        self.assertIn('ServerSocket(0, 16, InetAddress.getByName("127.0.0.1"))',s)
        self.assertIn('Connection: close',s)
        self.assertIn('Cache-Control: no-store',s)

    def test_both_screens_offer_mode_switch_and_style(self):
        for app, name in [('client','VexaMapView.kt'),('driver','DriverMap.kt')]:
            p = ROOT/f'android/{app}/app/src/main/java/ru/vexa/{app}/{name}'
            txt=p.read_text()
            for line in ('OfflineMbtilesServer(context)', 'Style.Builder().fromJson(json)',
                         'offlineSource.start()', 'OfflineMapMode.load(context)',
                         'Карта: ${mapMode.label}', 'styleVersion++'):
                with self.subTest(app=app,line=line): self.assertIn(line, txt)

    def test_offline_driver_does_not_fetch_online_route(self):
        src=(ROOT/'android/driver/app/src/main/java/ru/vexa/driver/DriverMap.kt').read_text()
        self.assertIn('if (offlineSelected)', src)
        self.assertIn('OfflineNavigation(context).route(', src)
        self.assertIn('routeLine = fetchDriverRoute(pickup, destination)', src)

    def test_raster_mode_selection_in_downloads(self):
        src=(SHARED/'OfflineMapsScreen.kt').read_text()
        self.assertIn('region.id in renderableRegions',src)
        self.assertIn('OfflineMapMode.selectRegion(context, region.id)',src)
        self.assertIn('Показать на карте',src)

    def test_android_release_cleartext_only_local(self):
        for app in ('client','driver'):
            path=ROOT/f'android/{app}/app/src/release/res/xml/vexa_network_security_config.xml'
            node=ET.parse(path).getroot()
            base=node.find('base-config'); self.assertEqual(base.attrib['cleartextTrafficPermitted'],'false')
            domains=node.findall('.//domain')
            self.assertEqual([d.text for d in domains], ['127.0.0.1'])
            self.assertEqual(node.find('domain-config').attrib['cleartextTrafficPermitted'],'true')

    def test_expected_mbtiles_xyz_tms_fixture(self):
        with tempfile.NamedTemporaryFile(suffix='.mbtiles') as tmp:
            db=sqlite3.connect(tmp.name)
            db.execute('create table metadata (name text, value text)')
            db.execute('create table tiles (zoom_level integer, tile_column integer, tile_row integer, tile_data blob)')
            db.execute('insert into metadata values (?,?)',('format','png'))
            # XYZ zoom=3 x=2 y=1 => MBTiles TMS row=6.
            db.execute('insert into tiles values (?,?,?,?)',(3,2,6,b'\x89PNGexample'))
            got=db.execute('select tile_data from tiles where zoom_level=? and tile_column=? and tile_row=?',
                           (3,2,(1<<3)-1-1)).fetchone()[0]
            self.assertEqual(got,b'\x89PNGexample')
            db.close()

    def test_offline_navigation_requires_navigation_index(self):
        screen=(SHARED/'OfflineMapsScreen.kt').read_text()
        self.assertIn('навигационного индекса VEXA v1',screen)
        self.assertIn('подготовленные векторные PBF работают без интернета',screen)

if __name__ == '__main__': unittest.main()
