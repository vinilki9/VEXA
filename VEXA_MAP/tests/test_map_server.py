"""VEXA MAP local server contract tests; no internet or map downloads required."""
import base64
import importlib.util
import json
import math
from io import BytesIO
from unittest.mock import patch
import sqlite3
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen, Request

MODULE = Path(__file__).resolve().parents[1] / 'server' / 'vexa_map_server.py'
sys.path.insert(0, str(MODULE.parent))
spec = importlib.util.spec_from_file_location('vexa_map_server', MODULE)
servermod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(servermod)

MAP_BACKGROUND = json.loads((MODULE.parents[1] / 'design-palette.json').read_text(encoding='utf-8'))['background']

PNG_1PIX = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/N6kAAAAASUVORK5CYII=')


class LocalVexaMapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.mbtiles = self.base / 'test.mbtiles'
        with sqlite3.connect(self.mbtiles) as db:
            db.execute('CREATE TABLE metadata (name TEXT, value TEXT)')
            db.executemany('INSERT INTO metadata VALUES (?, ?)', [('format', 'png'), ('minzoom', '0'), ('maxzoom', '2'), ('attribution', 'Synthetic test data')])
            db.execute('CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)')
            db.execute('INSERT INTO tiles VALUES (?, ?, ?, ?)', (0, 0, 0, PNG_1PIX))
            # z=2, y XYZ=1 -> TMS y=2. Ensures flip is correct.
            db.execute('INSERT INTO tiles VALUES (?, ?, ?, ?)', (2, 2, 2, PNG_1PIX))
        csv_path = self.base / 'places.csv'
        csv_path.write_text('name,latitude,longitude\nМосква,55.75,37.61\nТестовый адрес,54.98,37.22\n', encoding='utf-8')
        self.places = self.base / 'places.sqlite'
        servermod.import_places(csv_path, self.places)
        store = servermod.MapStore(str(self.mbtiles), str(self.places))
        self.srv = ThreadingHTTPServer(('127.0.0.1', 0), servermod.make_handler(store))
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        self.host = 'http://127.0.0.1:' + str(self.srv.server_port)

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def read_json(self, path):
        with urlopen(self.host + path, timeout=2) as r:
            return json.load(r)

    def test_health_reports_real_data(self):
        status = self.read_json('/health')
        self.assertTrue(status['map_ready'])
        self.assertTrue(status['search_ready'])
        self.assertFalse(status['routing_configured'])

    def test_raster_style_points_to_local_tiles(self):
        style = self.read_json('/style.json')
        self.assertEqual(style['version'], 8)
        self.assertEqual(style['layers'][0]['paint']['background-color'], MAP_BACKGROUND)
        self.assertEqual(style['sources']['vexa']['type'], 'raster')
        self.assertIn('/tiles/{z}/{x}/{y}.png', style['sources']['vexa']['tiles'][0])

    def test_tiles_flip_xyz_y(self):
        with urlopen(self.host + '/tiles/2/2/1.png', timeout=2) as r:
            self.assertEqual(r.read(), PNG_1PIX)
        with self.assertRaises(HTTPError) as e:
            urlopen(self.host + '/tiles/2/2/2.png', timeout=2)
        self.assertEqual(e.exception.code, 404)

    def test_search_from_own_index(self):
        data = self.read_json('/v1/search?q=%D0%9C%D0%BE%D1%81%D0%BA')
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['name'], 'Москва')

    def test_missing_osrm_is_explicit_503(self):
        with self.assertRaises(HTTPError) as e:
            urlopen(self.host + '/v1/route?start_lat=55.75&start_lon=37.61&end_lat=55.76&end_lon=37.62', timeout=2)
        self.assertEqual(e.exception.code, 503)
        self.assertIn('маршрут', e.exception.read().decode('utf-8').lower())


    def test_rejects_non_finite_route_coordinates_without_osrm_call(self):
        store = servermod.MapStore()
        for bad in (float('nan'), float('inf'), -float('inf'), 91.0):
            with self.subTest(value=str(bad)):
                with self.assertRaises(ValueError):
                    store.route(bad, 37.61, 55.76, 37.62)

    def test_route_http_rejects_nan_with_400(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.host + '/v1/route?start_lat=NaN&start_lon=37.61&end_lat=55.76&end_lon=37.62', timeout=2)
        self.assertEqual(error.exception.code, 400)

    def test_osrm_malformed_responses_do_not_become_valid_routes(self):
        store = servermod.MapStore(osrm_url='http://127.0.0.1:5000')
        bad_payloads = (
            {'code': 'Ok', 'routes': [{'distance': -1, 'duration': 4, 'geometry': {'type': 'LineString', 'coordinates': [[37, 55], [38, 56]]}}]},
            {'code': 'Ok', 'routes': [{'distance': 1, 'duration': float('nan'), 'geometry': {'type': 'LineString', 'coordinates': [[37, 55], [38, 56]]}}]},
            {'code': 'Ok', 'routes': [{'distance': 1, 'duration': 4, 'geometry': None}]},
            {'code': 'Ok', 'routes': [{'distance': 1, 'duration': 4, 'geometry': {'type': 'LineString', 'coordinates': [[37, 55]]}}]},
            {'code': 'Ok', 'routes': [{'distance': 1, 'duration': 4, 'geometry': {'type': 'LineString', 'coordinates': [[float('nan'), 55], [38, 56]]}}]},
        )
        for payload in bad_payloads:
            with self.subTest(payload=str(payload)[:90]):
                with patch.object(servermod, 'urlopen', return_value=BytesIO(json.dumps(payload).encode())):
                    with self.assertRaises(RuntimeError):
                        store.route(55.75, 37.61, 55.76, 37.62)

    def test_osrm_valid_response(self):
        store = servermod.MapStore(osrm_url='http://127.0.0.1:5000')
        route = {'code': 'Ok', 'routes': [{'distance': 1200.5, 'duration': 175, 'geometry': {'type': 'LineString', 'coordinates': [[37.61, 55.75], [37.62, 55.76]]}}]}
        with patch.object(servermod, 'urlopen', return_value=BytesIO(json.dumps(route).encode())):
            result = store.route(55.75, 37.61, 55.76, 37.62)
        self.assertEqual(result['distance_meters'], 1200.5)
        self.assertEqual(len(result['geometry']['coordinates']), 2)

    def test_osrm_maneuvers_are_structured_and_location_validated(self):
        store = servermod.MapStore(osrm_url='http://127.0.0.1:5000')
        step = lambda kind, location: {"name": "Тестовая улица", "distance": 120,
                                       "duration": 12, "maneuver": {"type": kind,
                                       "modifier": "right", "location": location}}
        route = {"code": "Ok", "routes": [{"distance": 200, "duration": 30,
            "geometry": {"type": "LineString", "coordinates": [[37.61, 55.75], [37.62, 55.76]]},
            "legs": [{"steps": [step("turn", [37.61, 55.75]),
                                step("turn", [float('nan'), 55.75]),
                                step("not-a-real-type", [37.62, 55.76])]}]}]}
        with patch.object(servermod, 'urlopen', return_value=BytesIO(json.dumps(route).encode())) as mocked:
            result = store.route(55.75, 37.61, 55.76, 37.62)
        self.assertEqual(result['routing_engine'], 'osrm')
        self.assertEqual(len(result['maneuvers']), 1)
        self.assertEqual(result['maneuvers'][0]['modifier'], 'right')
        self.assertIn('steps=true', mocked.call_args.args[0])

    def test_missing_data_does_not_fabricate_map(self):
        empty_store = servermod.MapStore()
        self.assertFalse(empty_store.map_ready)
        self.assertFalse(empty_store.search_ready)
        self.assertIsNone(empty_store.tile(0, 0, 0))


class RegionalRasterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.regions = self.root / "regions"
        self.regions.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def make_pack(self, name, tiles, fmt='png'):
        pack = self.regions / (name + '.mbtiles')
        with sqlite3.connect(pack) as db:
            db.execute('CREATE TABLE metadata (name TEXT, value TEXT)')
            db.executemany('INSERT INTO metadata VALUES (?, ?)',
                           [('format', fmt), ('minzoom', '0'), ('maxzoom', '4'),
                            ('attribution', 'Synthetic test data')])
            db.execute('CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)')
            db.executemany('INSERT INTO tiles VALUES (?, ?, ?, ?)', tiles)
        return pack

    def test_directory_loads_two_regions_and_tiles(self):
        self.make_pack('central', [(2, 2, 2, b'central'), (2, 1, 2, b'first')])
        self.make_pack('siberian', [(2, 3, 2, b'siberian'), (2, 1, 2, b'second')])
        store = servermod.MapStore(str(self.regions))
        self.assertEqual(store.package_count, 2)
        self.assertTrue(store.map_ready)
        self.assertEqual(store.tile(2, 2, 1), b'central')
        self.assertEqual(store.tile(2, 3, 1), b'siberian')
        self.assertEqual(store.tile(2, 1, 1), b'first')  # deterministic priority
        self.assertIsNone(store.tile(2, 3, 2))

    def test_mixed_raster_formats_rejected(self):
        self.make_pack('central', [], 'png')
        self.make_pack('siberian', [], 'webp')
        with self.assertRaisesRegex(ValueError, 'same format'):
            servermod.MapStore(str(self.regions))

    def test_pbf_is_not_pretended_to_be_renderable(self):
        self.make_pack('central', [], 'pbf')
        store = servermod.MapStore(str(self.regions))
        self.assertFalse(store.map_ready)
        self.assertTrue(store.vector_only)
        self.assertIsNone(store.tile(0, 0, 0))

    def test_vector_style_glyphs_and_driver_3d_on_http(self):
        import gzip
        glyph = b'\x0a\x02ab'
        pack = self.make_pack('central', [(0, 0, 0, gzip.compress(b'\x1a\x03xyz'))], 'pbf')
        with sqlite3.connect(pack) as db:
            db.execute('INSERT INTO metadata VALUES (?, ?)', ('json', json.dumps({'vector_layers': [
                {'id':'transportation'}, {'id':'transportation_name'},
                {'id':'building'}, {'id':'place'}, {'id':'water'}]})))
            db.execute('CREATE TABLE vexa_glyphs(fontstack TEXT,range_start INTEGER,pbf BLOB)')
            db.executemany('INSERT INTO vexa_glyphs VALUES(?,?,?)', [
                ('Noto Sans Regular', start, glyph) for start in (0, 256, 1024)])
        store = servermod.MapStore(str(self.regions))
        self.assertTrue(store.map_ready)
        self.assertTrue(store.vector_only)
        srv = ThreadingHTTPServer(('127.0.0.1', 0), servermod.make_handler(store))
        th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
        try:
            host = f'http://127.0.0.1:{srv.server_port}'
            with urlopen(host + '/style.json', timeout=2) as response:
                client_style = json.load(response)
            with urlopen(host + '/style.json?view=3d', timeout=2) as response:
                driver_style = json.load(response)
            for style in (client_style, driver_style):
                self.assertEqual(style['layers'][0]['paint']['background-color'], MAP_BACKGROUND)
            self.assertNotIn('fill-extrusion', [l['type'] for l in client_style['layers']])
            self.assertIn('fill-extrusion', [l['type'] for l in driver_style['layers']])
            self.assertEqual(client_style['sources']['vexa']['type'], 'vector')
            self.assertIn('/glyphs/{fontstack}/{range}.pbf', client_style['glyphs'])
            with urlopen(host + '/glyphs/Noto%20Sans%20Regular/1024-1279.pbf', timeout=2) as response:
                self.assertEqual(response.read(), glyph)
            with urlopen(host + '/tiles/0/0/0.pbf', timeout=2) as response:
                self.assertEqual(response.headers['Content-Encoding'], 'gzip')
                self.assertEqual(response.read()[:2], b'\x1f\x8b')
        finally:
            srv.shutdown(); srv.server_close(); th.join(timeout=2)

    def test_proxy_style_uses_maps_prefix(self):
        self.make_pack('central', [(0, 0, 0, PNG_1PIX)])
        store = servermod.MapStore(str(self.regions))
        srv = ThreadingHTTPServer(('127.0.0.1', 0), servermod.make_handler(store, trust_proxy=True))
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        try:
            req = Request('http://127.0.0.1:%d/style.json' % srv.server_port,
                          headers={'Host': 'localhost:8081', 'X-Forwarded-Prefix': '/maps',
                                   'X-Forwarded-Proto': 'https'})
            with urlopen(req, timeout=2) as response:
                style = json.load(response)
            url = style['sources']['vexa']['tiles'][0]
            self.assertEqual(url, 'https://localhost:8081/maps/tiles/{z}/{x}/{y}.png')
        finally:
            srv.shutdown()
            srv.server_close()
            thread.join(timeout=2)

    def test_proxy_headers_ignored_without_opt_in(self):
        self.make_pack('central', [])
        store = servermod.MapStore(str(self.regions))
        srv = ThreadingHTTPServer(('127.0.0.1', 0), servermod.make_handler(store))
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        try:
            req = Request('http://127.0.0.1:%d/style.json' % srv.server_port,
                          headers={'Host': 'localhost:8090', 'X-Forwarded-Prefix': '/maps',
                                   'X-Forwarded-Proto': 'https'})
            with urlopen(req, timeout=2) as response:
                style = json.load(response)
            self.assertEqual(style['sources']['vexa']['tiles'][0],
                             'http://localhost:8090/tiles/{z}/{x}/{y}.png')
        finally:
            srv.shutdown()
            srv.server_close()
            thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
