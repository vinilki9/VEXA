"""Local contract tests for VEXA MAP's versioned regional offline distribution."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SERVER_DIR = Path(__file__).resolve().parents[1] / "server"
sys.path.insert(0, str(SERVER_DIR))
from offline_packages import REGIONS, catalog, publish_region, read_manifest, verify_region

spec = importlib.util.spec_from_file_location("vexa_map_server_offline", SERVER_DIR / "vexa_map_server.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def make_test_region(directory: Path, region_id: str = "central") -> Path:
    path = directory / (region_id + ".mbtiles")
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
        db.executemany("INSERT INTO metadata VALUES (?, ?)",
                       [("format", "png"), ("minzoom", "0"), ("maxzoom", "2"),
                        ("attribution", "synthetic test set")])
        db.execute("CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)")
        db.execute("INSERT INTO tiles VALUES (0,0,0,?)", (b"synthetic tile, not real map data",))
    return path


class OfflinePackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.pack = make_test_region(self.dir)
        self.manifest = publish_region(self.dir, "central", "2026.11")
        self.store = mod.MapStore(str(self.dir), offline_downloads=True)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), mod.make_handler(self.store))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def request(self, endpoint, headers=None, method="GET"):
        return urlopen(Request(self.base + endpoint, headers=headers or {}, method=method), timeout=3)

    def test_catalog_contains_all_eight_districts(self):
        with self.request("/v1/offline/catalog") as response:
            data = json.load(response)
        self.assertEqual(len(data["regions"]), 8)
        self.assertEqual(sum(1 for r in data["regions"] if r["available"]), 1)
        published = next(r for r in data["regions"] if r["region_id"] == "central")
        self.assertEqual(published["size_bytes"], self.pack.stat().st_size)
        self.assertTrue(published["download_url"].endswith("/central/download"))
        self.assertIn("far-eastern", REGIONS)
        self.assertEqual(catalog(None)[0]["available"], False)

    def test_manifest_and_full_download(self):
        with self.request("/v1/offline/regions/central/manifest") as response:
            data = json.load(response)
        self.assertEqual(data["sha256"], self.manifest["sha256"])
        with self.request("/v1/offline/regions/central/download") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Content-Length"], str(self.pack.stat().st_size))
            self.assertEqual(response.headers["Accept-Ranges"], "bytes")
            payload = response.read()
        self.assertEqual(payload, self.pack.read_bytes())
        self.assertTrue(verify_region(self.dir, "central"))

    def test_resumable_ranges_and_etag(self):
        url = "/v1/offline/regions/central/download"
        with self.request(url, {"Range": "bytes=0-23"}) as response:
            self.assertEqual(response.status, 206)
            start = response.read()
            self.assertEqual(start, self.pack.read_bytes()[:24])
            self.assertTrue(response.headers["Content-Range"].startswith("bytes 0-23/"))
            etag = response.headers["ETag"]
        with self.request(url, {"Range": "bytes=24-", "If-Range": etag}) as response:
            self.assertEqual(response.status, 206)
            remainder = response.read()
        self.assertEqual(start + remainder, self.pack.read_bytes())
        with self.request(url, {"Range": "bytes=-12"}) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), self.pack.read_bytes()[-12:])
        with self.request(url, {"Range": "bytes=24-", "If-Range": '"old-digest"'}) as response:
            self.assertEqual(response.status, 200)
        with self.assertRaises(HTTPError) as error:
            self.request(url, {"Range": "bytes=99999999999999999-"})
        self.assertEqual(error.exception.code, 416)
        with self.assertRaises(HTTPError) as unchanged:
            self.request(url, {"If-None-Match": etag})
        self.assertEqual(unchanged.exception.code, 304)

    def test_head_and_invalid_requests(self):
        with self.request("/v1/offline/regions/central/download", method="HEAD") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"")
            self.assertEqual(response.headers["Content-Length"], str(self.pack.stat().st_size))
        with self.assertRaises(HTTPError) as error:
            self.request("/v1/offline/regions/../../etc/passwd/download")
        self.assertEqual(error.exception.code, 404)
        with self.assertRaises(HTTPError) as error:
            self.request("/v1/offline/regions/unknown/download")
        self.assertEqual(error.exception.code, 404)
        with self.assertRaises(HTTPError) as error:
            self.request("/v1/offline/catalog", method="HEAD")
        self.assertEqual(error.exception.code, 405)

    def test_download_is_explicitly_disabled_by_default(self):
        disabled = mod.MapStore(str(self.dir))
        server = ThreadingHTTPServer(("127.0.0.1", 0), mod.make_handler(disabled))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(HTTPError) as error:
                urlopen(f"http://127.0.0.1:{server.server_port}/v1/offline/regions/central/download")
            self.assertEqual(error.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_missing_or_corrupt_manifest_not_published(self):
        self.assertFalse(verify_region(self.dir, "volga"))
        self.assertIsNone(read_manifest(self.dir, "volga"))
        m = self.dir / "central.manifest.json"
        data = json.loads(m.read_text())
        data["size_bytes"] = -7
        m.write_text(json.dumps(data))
        self.assertIsNone(read_manifest(self.dir, "central"))
        self.assertFalse(verify_region(self.dir, "central"))

    def test_corruption_detected_on_explicit_full_verify(self):
        original = self.pack.read_bytes()
        # Modifying bytes without changing size must be detected via digest.
        self.pack.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        self.assertIsNotNone(read_manifest(self.dir, "central"))
        self.assertFalse(verify_region(self.dir, "central"))

    def test_region_and_version_validation(self):
        with self.assertRaises(ValueError):
            publish_region(self.dir, "../../outside", "1.0")
        with self.assertRaises(ValueError):
            publish_region(self.dir, "central", "hello world")
        with self.assertRaises(ValueError):
            publish_region(self.dir, "northwestern", "1.0")  # no MBTiles
        self.assertIsNone(read_manifest(self.dir, "northwestern"))


if __name__ == "__main__":
    unittest.main()
