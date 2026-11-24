"""Only synthetic fixtures and test binaries. No OSM download or real routing."""
from pathlib import Path
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest

TOOL_DIR = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOL_DIR))
import build_region_0320 as build


class RegionPipelineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name)
        self.source = self.path / 'central-latest.osm.pbf'
        self.source.write_bytes(b'NOT REAL OSM DATA - synthetic test\n' * 50)
        self.config = self.path / 'config-openmaptiles.json'
        self.config.write_text('{}', encoding='utf-8')
        self.lua = self.path / 'process-openmaptiles.lua'
        self.lua.write_text('return 1\n', encoding='utf-8')
        self.profile = self.path / 'car.lua'
        self.profile.write_text('return {}\n', encoding='utf-8')
        self.builds = self.path / 'builds'
        self.bin = self.path / 'bin'
        self.bin.mkdir()

    def shim(self, name: str, program: str):
        path = self.bin / name
        path.write_text('#!/usr/bin/env python3\n' + program + '\n')
        path.chmod(0o755)
        return str(path)

    def plan(self, profile=None, tilemaker='tilemaker', osrm_prefix=''):
        return build.build_plan('central', '2026.11', self.source, self.builds,
                                self.config, self.lua, profile, 250, 0,
                                tilemaker, osrm_prefix)

    def test_eight_regions_and_correct_geofabrik_paths(self):
        self.assertEqual(len(build.REGIONS), 8)
        self.assertEqual(build.source_url('central'),
                         'https://download.geofabrik.de/russia/central-fed-district-latest.osm.pbf')
        self.assertIn('/south-fed-district-latest.osm.pbf', build.source_url('southern'))
        self.assertIn('/far-eastern-fed-district-latest.osm.pbf', build.source_url('far-eastern'))

    def test_plan_does_not_create_data_or_download(self):
        dummy = self.shim('tilemaker-dry', 'import sys; sys.exit(0)')
        result = self.plan(tilemaker=dummy)
        self.assertTrue(result['input_exists'])
        self.assertTrue(result['ready_for_execution'])
        self.assertEqual(len(result['commands']), 1)
        self.assertFalse(self.builds.exists())

    def test_source_integrity_and_validation(self):
        safe_tool = self.shim('tilemaker-safe', 'import sys; sys.exit(0)')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            build.execute_plan(self.plan(tilemaker=safe_tool), expected_sha256='a' * 64)
        self.assertFalse(self.builds.exists())
        with self.assertRaisesRegex(ValueError, 'бюджет'):
            build.validate_params('central', 'v1', 251, 10)
        with self.assertRaisesRegex(ValueError, 'верс'):
            build.validate_params('central', '../v1', 250, 10)
        self.assertTrue(build.sha256(self.source))

    def test_missing_binaries_prevent_writes(self):
        plan = self.plan(tilemaker='missing-tilemaker-test-not-installed')
        self.assertEqual(plan['missing_tools'], ['missing-tilemaker-test-not-installed'])
        with self.assertRaisesRegex(ValueError, 'инструменты'):
            build.execute_plan(plan)
        self.assertFalse(self.builds.exists())

    def test_build_vector_and_osrm_without_touching_original(self):
        fake_tilemaker = self.shim('tilemaker-test', '''import sqlite3, json, sys
from pathlib import Path
args = sys.argv
out = Path(args[args.index('--output')+1])
with sqlite3.connect(out) as db:
  db.execute('CREATE TABLE metadata(name TEXT,value TEXT)')
  db.execute('CREATE TABLE tiles(zoom_level INT, tile_column INT, tile_row INT, tile_data BLOB)')
  db.executemany('INSERT INTO metadata VALUES(?,?)', [('format','pbf'),('minzoom','0'),('maxzoom','14'),('json',json.dumps({'vector_layers':[{'id':'transportation'},{'id':'place'},{'id':'building'}]})),('attribution','© OpenStreetMap contributors')])
  db.execute('INSERT INTO tiles VALUES(0,0,0,?)',(b'\\x1a\\x01z',))''')
        self.shim('osrm-extract', '''from pathlib import Path
import sys
p=Path(sys.argv[-1]); Path(str(p).replace('.osm.pbf','.osrm')).write_bytes(b'OSRMTEST')''')
        self.shim('osrm-partition', 'import sys; from pathlib import Path; assert Path(sys.argv[-1]).is_file()')
        self.shim('osrm-customize', 'import sys; from pathlib import Path; assert Path(sys.argv[-1]).is_file()')
        p = self.plan(self.profile, fake_tilemaker, str(self.bin) + '/')
        self.assertEqual(p['missing_tools'], [])
        receipt = build.execute_plan(p, expected_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest())
        result = Path(receipt['output'])
        self.assertTrue((result / 'map.mbtiles').is_file())
        self.assertTrue((result / 'osrm' / 'region.osrm').is_file())
        self.assertEqual(receipt['vector_layers'], ['transportation', 'place', 'building'])
        self.assertFalse((self.path / 'builds' / '.central-2026.11.pending').exists())
        with sqlite3.connect(result / 'map.mbtiles') as db:
            self.assertEqual(db.execute("SELECT value FROM metadata WHERE name='vexa_region_id'").fetchone()[0], 'central')
        self.assertTrue((result / 'build-receipt.json').is_file())
        self.assertTrue(self.source.is_file())
        again = self.plan(self.profile, fake_tilemaker, str(self.bin) + '/')
        self.assertFalse(again['ready_for_execution'])
        with self.assertRaisesRegex(ValueError, 'Preflight'):
            build.execute_plan(again)

    def test_failure_preserves_staging_logs_not_published(self):
        broken = self.shim('tilemaker-broken', 'import sys; print("test failed to build"); sys.exit(6)')
        plan = self.plan(tilemaker=broken)
        with self.assertRaisesRegex(RuntimeError, 'код завершения 6'):
            build.execute_plan(plan)
        self.assertFalse(Path(plan['output']).exists())
        self.assertIn('test failed', (Path(plan['staging']) / 'vector.log').read_text())
        self.assertTrue(self.source.is_file())

    def test_disk_projection_estimates_not_promises(self):
        self.assertGreater(build.disk_projection(100 * 1024**2, True),
                           build.disk_projection(100 * 1024**2, False))
        plan = self.plan()
        self.assertTrue(plan['estimated_not_guaranteed'])
        self.assertGreater(plan['estimated_extra_bytes'], 0)


if __name__ == '__main__':
    unittest.main()
