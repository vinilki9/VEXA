"""Synthetic MBTiles/glyphs only; does not download or redistribute maps/fonts."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'prepare_vector_mbtiles.py'
spec = importlib.util.spec_from_file_location('prepare_vector_mbtiles_0319', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PbfPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.tile = self.base / 'central.mbtiles'
        with sqlite3.connect(self.tile) as db:
            db.execute('CREATE TABLE metadata(name TEXT,value TEXT)')
            db.executemany('INSERT INTO metadata VALUES(?,?)', [
                ('format', 'pbf'), ('json', json.dumps({'vector_layers': [
                    {'id': 'transportation'}, {'id': 'place'}, {'id': 'building'}]}))])
            db.execute('CREATE TABLE tiles(zoom_level INTEGER,tile_column INTEGER,tile_row INTEGER,tile_data BLOB)')
            db.execute('INSERT INTO tiles VALUES(0,0,0,?)', (b'\x1a\x03abc',))

    def test_vector_metadata_accepted_without_font_assets(self):
        result = mod.prepare(self.tile, 'central')
        self.assertEqual(result['vector_layers'], ['transportation', 'place', 'building'])
        self.assertEqual(result['glyph_ranges'], 0)
        with sqlite3.connect(self.tile) as db:
            self.assertEqual(db.execute("SELECT value FROM metadata WHERE name='vexa_region_id'").fetchone()[0], 'central')

    def test_vector_missing_road_layer_rejected(self):
        with sqlite3.connect(self.tile) as db:
            db.execute("UPDATE metadata SET value=? WHERE name='json'", (json.dumps({'vector_layers': [{'id':'place'}]}),))
        with self.assertRaisesRegex(ValueError, 'road'):
            mod.prepare(self.tile, 'central')

    def test_raster_rejected_without_touching_existing_tiles(self):
        with sqlite3.connect(self.tile) as db:
            db.execute("UPDATE metadata SET value='png' WHERE name='format'")
        with self.assertRaisesRegex(ValueError, 'pbf'):
            mod.prepare(self.tile, 'central')
        with sqlite3.connect(self.tile) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tiles').fetchone()[0], 1)

    def test_embedding_and_idempotence(self):
        font = self.base / 'glyphs' / 'Noto Sans Regular'
        font.mkdir(parents=True)
        for start in mod.REQUIRED_RANGES:
            (font / f'{start}-{start+255}.pbf').write_bytes(b'\x0a\x02ab')
        for _ in range(2):
            result = mod.prepare(self.tile, 'central', self.base / 'glyphs')
            self.assertEqual(result['glyph_ranges'], 3)
        with sqlite3.connect(self.tile) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM vexa_glyphs').fetchone()[0], 3)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tiles').fetchone()[0], 1)

    def test_missing_cyrillic_font_fails_before_db_mutation(self):
        font = self.base / 'glyphs' / 'Noto Sans Regular'
        font.mkdir(parents=True)
        (font / '0-255.pbf').write_bytes(b'\x0a\x02ab')
        with self.assertRaisesRegex(ValueError, 'ranges'):
            mod.prepare(self.tile, 'central', self.base / 'glyphs')
        with sqlite3.connect(self.tile) as db:
            self.assertIsNone(db.execute("SELECT value FROM metadata WHERE name='vexa_region_id'").fetchone())


if __name__ == '__main__':
    unittest.main()
