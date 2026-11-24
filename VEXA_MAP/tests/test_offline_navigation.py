"""Contract tests for optional v1 address + directed road schema (synthetic test data only)."""
from __future__ import annotations

import csv
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from prepare_offline_navigation import install, tokens


class OfflineNavigationSchemaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.mbtiles = root / 'central.mbtiles'
        with sqlite3.connect(self.mbtiles) as db:
            db.execute('CREATE TABLE metadata(name TEXT, value TEXT)')
            db.execute('INSERT INTO metadata VALUES(?,?)', ('format', 'png'))
            db.execute('CREATE TABLE tiles(zoom_level INTEGER,tile_column INTEGER,tile_row INTEGER,tile_data BLOB)')
            db.execute('INSERT INTO tiles VALUES (0,0,0,?)', (b'synthetic-tile',))
        self.places = root / 'places.csv'
        self.nodes = root / 'nodes.csv'
        self.edges = root / 'edges.csv'
        self._csv(self.places, ['name','latitude','longitude','rank'], [
            ['Москва, улица Ленина 8', 55.75, 37.61, 20],
            ['Дом на Тверской', 55.76, 37.63, 10]])
        self._csv(self.nodes, ['node_id','latitude','longitude'], [
            [1,55.750,37.610], [2,55.750,37.620], [3,55.760,37.630]])
        self._csv(self.edges, ['source_id','target_id','distance_m','duration_s'], [
            [1,2,700,70], [2,3,1300,130]])

    def _csv(self, file, headers, rows):
        with file.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream); writer.writerow(headers); writer.writerows(rows)

    def test_install_indexes_existing_mbtiles_without_overwriting_tiles(self):
        result = install(self.mbtiles, 'central', self.places, self.nodes, self.edges)
        self.assertEqual((result['places'], result['nodes'], result['directed_edges']), (2,3,2))
        with sqlite3.connect(self.mbtiles) as db:
            self.assertEqual(db.execute('SELECT tile_data FROM tiles').fetchone()[0], b'synthetic-tile')
            self.assertEqual(db.execute("SELECT value FROM metadata WHERE name='vexa_region_id'").fetchone()[0], 'central')
            self.assertEqual(db.execute("SELECT value FROM metadata WHERE name='vexa_navigation_schema'").fetchone()[0], 'v1')
            matches = list(db.execute('SELECT p.name FROM vexa_terms t JOIN vexa_places p ON t.place_id=p.place_id WHERE t.term>=? AND t.term<?', ('лен','лен\uffff')))
            self.assertEqual(matches, [('Москва, улица Ленина 8',)])
            self.assertEqual(db.execute('SELECT count(*) FROM vexa_edges').fetchone()[0], 2)
            self.assertEqual(db.execute('SELECT count(*) FROM vexa_node_rtree').fetchone()[0], 3)
            self.assertEqual(db.execute('SELECT node_id FROM vexa_node_rtree WHERE min_lat<=? AND max_lat>=? AND min_lon<=? AND max_lon>=?', (55.751,55.749,37.621,37.609)).fetchall(), [(1,), (2,)])

    def test_spatial_index_rebuild_is_atomic(self):
        install(self.mbtiles, 'central', self.places, self.nodes, self.edges)
        self._csv(self.edges, ['source_id','target_id','distance_m','duration_s'], [[1,999,100,10]])
        with self.assertRaises(ValueError):
            install(self.mbtiles, 'central', self.places, self.nodes, self.edges)
        with sqlite3.connect(self.mbtiles) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM vexa_node_rtree').fetchone()[0], 3)

    def test_rebuild_has_no_duplicate_terms(self):
        install(self.mbtiles, 'central', self.places, self.nodes, self.edges)
        install(self.mbtiles, 'central', self.places, self.nodes, self.edges)
        with sqlite3.connect(self.mbtiles) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM vexa_places').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT count(*) FROM vexa_edges').fetchone()[0],2)

    def test_invalid_edges_roll_back_without_destroying_existing_index(self):
        install(self.mbtiles, 'central', self.places, self.nodes, self.edges)
        self._csv(self.edges, ['source_id','target_id','distance_m','duration_s'], [[1,999,100,10]])
        with self.assertRaisesRegex(ValueError, 'missing node'):
            install(self.mbtiles, 'central', self.places, self.nodes, self.edges)
        with sqlite3.connect(self.mbtiles) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM vexa_edges').fetchone()[0],2)

    def test_bad_coordinates_rejected(self):
        self._csv(self.places, ['name','latitude','longitude','rank'], [['X',91,12,1]])
        with self.assertRaisesRegex(ValueError, 'invalid latitude'):
            install(self.mbtiles, 'central', self.places, self.nodes, self.edges)

    def test_unknown_region_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unknown'):
            install(self.mbtiles, '../tmp', self.places, self.nodes, self.edges)

    def test_token_normalization(self):
        self.assertEqual(tokens('Ёлка, Ленина 8!'), ['елка','ленина','8'])


if __name__ == '__main__': unittest.main()
