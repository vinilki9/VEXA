"""VEXA MAP local HTTP service: raster/vector MBTiles, offline place search, OSRM routing.

Standard-library server intentionally separate from VEXA Backend.
It contains no map tiles, places or route graph: import data before production use.
"""
from __future__ import annotations

import argparse
from offline_packages import REGIONS, catalog, publish_region, read_manifest, verify_region
import csv
from contextlib import closing
import json
from math import isfinite
import os
import re
import sqlite3
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import urlopen

MAX_QUERY = 160
MAX_ZOOM = 22


class MapStore:
    """Read one raster MBTiles or a directory of district-sized MBTiles.

    Every regional pack must use the same tile format and vector source-layer schema.
    Packs are inspected in sorted filename order; earlier packs win on overlap.
    Vector style can show roads and optional local glyph labels/3D buildings.
    """

    def __init__(self, mbtiles: str = "", places: str = "", osrm_url: str = "", offline_downloads: bool = False):
        requested = Path(mbtiles).expanduser() if mbtiles else None
        self.places = Path(places).expanduser() if places else None
        self.osrm_url = osrm_url.strip().rstrip("/")
        self.offline_directory = (requested.resolve() if requested is not None and requested.is_dir()
                                  else requested.resolve().parent if requested is not None and requested.is_file()
                                  else None)
        self.offline_downloads = bool(offline_downloads)
        self.packages: list[Path] = []
        self.format = ""
        self.tile_mime = ""
        self.minzoom = 0
        self.maxzoom = 18
        self.attribution = ""
        self.vector_only = False
        self.vector_layers: set[str] = set()
        self.vector_labels = False
        candidates = (
            sorted(path for path in requested.glob("*.mbtiles") if path.is_file())
            if requested is not None and requested.is_dir()
            else [requested] if requested is not None and requested.is_file() else []
        )
        for path in candidates:
            with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as db:
                meta = dict(db.execute("SELECT name, value FROM metadata"))
            fmt = meta.get("format", "png").lower()
            if fmt == "jpeg":
                fmt = "jpg"
            if fmt not in ("png", "jpg", "webp", "pbf"):
                raise ValueError(f"Unsupported MBTiles format in {path.name}: {fmt}")
            if self.format and self.format != fmt:
                raise ValueError("Regional packages must have the same format: "
                                 f"{path.name} is {fmt}, expected {self.format}")
            if fmt == 'pbf':
                try:
                    layer_info = json.loads(meta.get('json', '{}'))['vector_layers']
                    layer_ids = {layer['id'] for layer in layer_info if isinstance(layer, dict)}
                    if not layer_ids or not all(isinstance(i, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', i) for i in layer_ids):
                        layer_ids = set()
                except (ValueError, TypeError, KeyError):
                    layer_ids = set()
                if self.packages and layer_ids != self.vector_layers:
                    raise ValueError('Regional vector packages must use the same source-layer schema')
                self.vector_layers = layer_ids
                try:
                    with closing(sqlite3.connect(f'file:{path}?mode=ro', uri=True)) as db:
                        glyph_ranges = {int(row[0]) for row in db.execute(
                            "SELECT range_start FROM vexa_glyphs WHERE fontstack='Noto Sans Regular' "
                            "AND range_start IN (0,256,1024) AND length(pbf) BETWEEN 1 AND 2097152")}
                        self.vector_labels = self.vector_labels or {0, 256, 1024}.issubset(glyph_ranges)
                except sqlite3.DatabaseError:
                    pass
            minzoom = int(meta.get("minzoom", "0"))
            maxzoom = int(meta.get("maxzoom", "18"))
            if not (0 <= minzoom <= maxzoom <= MAX_ZOOM):
                raise ValueError(f"Invalid zoom range in {path.name}")
            self.minzoom = min(self.minzoom, minzoom) if self.packages else minzoom
            self.maxzoom = max(self.maxzoom, maxzoom) if self.packages else maxzoom
            self.format = fmt
            self.attribution = meta.get("attribution", "© OpenStreetMap contributors")
            self.packages.append(path)
        self.vector_only = self.format == "pbf"
        self.tile_mime = {"png": "image/png", "jpg": "image/jpeg",
                          "webp": "image/webp", "pbf": "application/x-protobuf"}.get(self.format, "")

    @property
    def map_ready(self):
        # PBF without metadata.json.vector_layers has no safe way to select source-layers.
        return bool(self.packages) and (not self.vector_only or bool({'transportation','road'}.intersection(self.vector_layers)))

    @property
    def package_count(self):
        return len(self.packages)

    @property
    def search_ready(self):
        if not self.places or not self.places.is_file():
            return False
        try:
            with closing(sqlite3.connect(f"file:{self.places}?mode=ro", uri=True)) as db:
                return db.execute("SELECT 1 FROM places LIMIT 1").fetchone() is not None
        except sqlite3.DatabaseError:
            return False

    def glyph(self, fontstack: str, start: int) -> bytes | None:
        """Only locally embedded licensed glyph ranges; never fetch external font services."""
        if not self.vector_only or fontstack != 'Noto Sans Regular' or start not in range(0, 65536, 256):
            return None
        for path in self.packages:
            try:
                with closing(sqlite3.connect(f'file:{path}?mode=ro', uri=True)) as db:
                    row = db.execute('SELECT pbf FROM vexa_glyphs WHERE fontstack=? AND range_start=?',
                                     (fontstack, start)).fetchone()
                if row and 0 < len(row[0]) <= 2 * 1024 * 1024:
                    return row[0]
            except sqlite3.DatabaseError:
                continue
        return None

    def vector_style(self, origin: str, buildings3d: bool = False) -> dict:
        if not (self.vector_only and self.map_ready):
            raise ValueError('No renderable vector packs')
        ls = [{'id': 'background', 'type': 'background', 'paint': {'background-color': '#151D21'}}]
        def add(layer_id: str, layer_type: str, source_layer: str, paint: dict, zoom: int = 0, layout: dict | None = None):
            layer = {'id': layer_id, 'type': layer_type, 'source': 'vexa',
                     'source-layer': source_layer, 'paint': paint, 'minzoom': zoom}
            if layout:
                layer['layout'] = layout
            ls.append(layer)
        if 'landcover' in self.vector_layers:
            add('landcover', 'fill', 'landcover', {'fill-color': '#26372F', 'fill-opacity': 0.55})
        if 'landuse' in self.vector_layers:
            add('landuse', 'fill', 'landuse', {'fill-color': '#23332E', 'fill-opacity': 0.55})
        if 'water' in self.vector_layers:
            add('water', 'fill', 'water', {'fill-color': '#183E48'})
        road = next((layer for layer in ('transportation', 'road') if layer in self.vector_layers), None)
        if road:
            add('road-casing', 'line', road, {'line-color': '#0D171A', 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.4, 15, 6.0]}, 5)
            add('roads', 'line', road, {'line-color': '#5D797B', 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.5, 15, 4.0]}, 5)
        if 'building' in self.vector_layers:
            if not buildings3d:
                add('buildings-flat', 'fill', 'building', {'fill-color': '#35494B', 'fill-opacity': 0.75}, 13)
            else:
                add('buildings-3d', 'fill-extrusion', 'building', {
                    'fill-extrusion-color': '#476467', 'fill-extrusion-opacity': 0.85,
                    'fill-extrusion-height': ['max', 3, ['coalesce', ['to-number', ['get', 'render_height']],
                                                     ['to-number', ['get', 'height']], 9]]}, 14)
        if self.vector_labels:
            text_layout = {'text-field': ['coalesce', ['get', 'name:ru'], ['get', 'name'], ''],
                           'text-font': ['Noto Sans Regular'], 'text-size': 12, 'text-max-width': 8}
            text_paint = {'text-color': '#D7E7E6', 'text-halo-color': '#151D21', 'text-halo-width': 1.5}
            if 'transportation_name' in self.vector_layers:
                add('street-labels', 'symbol', 'transportation_name', text_paint, 12, text_layout)
            elif road:
                add('street-labels', 'symbol', road, text_paint, 14, text_layout)
            if 'place' in self.vector_layers:
                add('place-labels', 'symbol', 'place', text_paint, 5, text_layout)
        style = {'version': 8, 'name': 'VEXA MAP vector', 'sources': {
            'vexa': {'type': 'vector', 'tiles': [f'{origin}/tiles/{{z}}/{{x}}/{{y}}.pbf'],
                     'minzoom': self.minzoom, 'maxzoom': self.maxzoom, 'attribution': self.attribution}},
                 'layers': ls}
        if self.vector_labels:
            style['glyphs'] = f'{origin}/glyphs/{{fontstack}}/{{range}}.pbf'
        return style

    def tile(self, z: int, x: int, y: int) -> bytes | None:
        if not self.map_ready or z < self.minzoom or z > self.maxzoom or z > MAX_ZOOM:
            return None
        if not (0 <= x < 2 ** z and 0 <= y < 2 ** z):
            return None
        tms_y = (2 ** z - 1) - y  # MBTiles stores tile_row as TMS
        for path in self.packages:
            with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as db:
                row = db.execute(
                    "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                    (z, x, tms_y),
                ).fetchone()
            if row is not None:
                return row[0]
        return None

    def search(self, query: str) -> list[dict]:
        if not self.search_ready:
            raise RuntimeError("Адресный индекс VEXA MAP ещё не загружен")
        query = query.strip()
        if not query or len(query) > MAX_QUERY:
            return []
        # LIKE parameters are escaped. Not FTS ranking; simple offline starter index.
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with closing(sqlite3.connect(f"file:{self.places}?mode=ro", uri=True)) as db:
            rows = db.execute(
                "SELECT name, latitude, longitude FROM places "
                "WHERE name_search LIKE ? ESCAPE '\\' ORDER BY length(name), name LIMIT 10",
                ("%" + escaped.casefold() + "%",),
            ).fetchall()
        return [{"name": name, "latitude": lat, "longitude": lon} for name, lat, lon in rows]

    def route(self, start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> dict:
        coords = (start_lat, start_lon, end_lat, end_lon)
        if (not all(isfinite(c) for c in coords) or
                not (-90 <= start_lat <= 90 and -90 <= end_lat <= 90 and
                     -180 <= start_lon <= 180 and -180 <= end_lon <= 180)):
            raise ValueError("Некорректные координаты")
        if not self.osrm_url:
            raise RuntimeError("Маршрутизация не настроена: нужен локальный OSRM с дорожным графом")
        coords = f"{start_lon},{start_lat};{end_lon},{end_lat}"
        url = f"{self.osrm_url}/route/v1/driving/{coords}?overview=full&geometries=geojson&steps=true"
        with urlopen(url, timeout=12) as response:
            data = json.load(response)
        if not isinstance(data, dict) or data.get("code") != "Ok" or not isinstance(data.get("routes"), list) or not data["routes"]:
            raise RuntimeError("Маршрут не найден в локальном дорожном графе")
        route = data["routes"][0]
        if not isinstance(route, dict):
            raise RuntimeError("Некорректный ответ OSRM")
        distance, duration = route.get("distance"), route.get("duration")
        if (type(distance) not in (int, float) or type(duration) not in (int, float) or
                not isfinite(distance) or not isfinite(duration) or
                distance < 0 or duration < 0):
            raise RuntimeError("OSRM вернул некорректные расстояние или время")
        geometry = route.get("geometry", {})
        points = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if (not isinstance(geometry, dict) or geometry.get("type") != "LineString" or
                not isinstance(points, list) or len(points) < 2 or
                any(not isinstance(point, list) or len(point) < 2 or
                    any(type(c) not in (int, float) or not isfinite(c) for c in point[:2]) or
                    not (-180 <= point[0] <= 180 and -90 <= point[1] <= 90)
                    for point in points)):
            raise RuntimeError("OSRM вернул некорректную геометрию маршрута")
        # A production OSRM instance can provide turn maneuvers; keep them structured.
        # The app still needs GPS progress matching and rerouting before live voice guidance.
        maneuvers = []
        for leg in route.get("legs", []) if isinstance(route.get("legs", []), list) else []:
            if not isinstance(leg, dict):
                continue
            for step in leg.get("steps", []) if isinstance(leg.get("steps", []), list) else []:
                if not isinstance(step, dict) or len(maneuvers) >= 2000:
                    continue
                info = step.get("maneuver")
                if not isinstance(info, dict):
                    continue
                kind, modifier = info.get("type"), info.get("modifier")
                position = info.get("location")
                if kind not in {"depart", "arrive", "turn", "new name", "merge", "on ramp", "off ramp",
                                "fork", "end of road", "continue", "roundabout", "rotary", "roundabout turn",
                                "notification", "exit rotary"}:
                    continue
                if modifier not in {"uturn", "sharp right", "right", "slight right", "straight",
                                    "slight left", "left", "sharp left", None}:
                    modifier = None
                if (not isinstance(position, list) or len(position) < 2 or
                        any(type(v) not in (int, float) or not isfinite(v) for v in position[:2]) or
                        not (-180 <= position[0] <= 180 and -90 <= position[1] <= 90)):
                    continue
                step_distance = step.get("distance", 0)
                step_duration = step.get("duration", 0)
                if (type(step_distance) not in (int, float) or type(step_duration) not in (int, float) or
                        not isfinite(step_distance) or not isfinite(step_duration) or
                        step_distance < 0 or step_duration < 0):
                    continue
                name = step.get("name", "")
                maneuvers.append({"type": kind, "modifier": modifier, "road_name": name[:160] if isinstance(name, str) else "",
                                  "longitude": position[0], "latitude": position[1],
                                  "distance_meters": step_distance, "duration_seconds": step_duration})
        return {"distance_meters": distance, "duration_seconds": duration,
                "geometry": geometry, "routing_engine": "osrm", "maneuvers": maneuvers}


def make_handler(store: MapStore, public_base: str = "", trust_proxy: bool = False):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            print(f"[VEXA MAP] {self.address_string()} " + fmt % args)

        def send_bytes(self, content: bytes, mime: str, status: int = 200, cache_seconds: int = 0):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", f"public, max-age={cache_seconds}" if cache_seconds else "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)

        def send_json(self, obj, status=200):
            self.send_bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

        def send_offline_file(self, region_id: str, manifest: dict, head_only: bool = False):
            """Stream downloads and one RFC7233 byte-range (supports interrupted transfers)."""
            path = store.offline_directory / manifest["file_name"]
            size = manifest["size_bytes"]
            etag = '"' + manifest["sha256"] + '"'
            if not self.headers.get("Range") and self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.end_headers()
                return
            requested = self.headers.get("Range", "")
            if requested and self.headers.get("If-Range") not in (None, etag):
                requested = ""  # changed version -> download full new file
            first, last = 0, size - 1
            partial = bool(requested)
            if requested:
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
                if match is None or not (match[1] or match[2]):
                    return self.range_not_satisfiable(size)
                if match[1]:
                    first = int(match[1])
                    last = int(match[2]) if match[2] else size - 1
                else:
                    count = int(match[2])
                    if count == 0:
                        return self.range_not_satisfiable(size)
                    first = max(0, size - count)
                if first >= size or last < first:
                    return self.range_not_satisfiable(size)
                last = min(last, size - 1)
            length = last - first + 1
            self.send_response(206 if partial else 200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{region_id}.mbtiles"')
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if partial:
                self.send_header("Content-Range", f"bytes {first}-{last}/{size}")
            self.end_headers()
            if head_only:
                return
            try:
                with path.open("rb") as file:
                    file.seek(first)
                    remaining = length
                    while remaining > 0:
                        chunk = file.read(min(256 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                return  # client paused the transfer; a later Range request can resume

        def range_not_satisfiable(self, size: int):
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_HEAD(self):
            self.handle_request(head_only=True)

        def do_GET(self):
            self.handle_request(head_only=False)

        def handle_request(self, head_only: bool = False):
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query, keep_blank_values=True)
            host = self.headers.get('Host', '127.0.0.1:8090')
            if not re.fullmatch(r"[A-Za-z0-9.:-]+", host):
                host = '127.0.0.1:8090'
            origin = public_base.rstrip("/") or f"http://{host}"
            # Only honor proxy headers when explicitly running behind our local Nginx.
            if not public_base and trust_proxy and self.headers.get("X-Forwarded-Prefix") == "/maps":
                scheme = self.headers.get("X-Forwarded-Proto", "http").lower()
                if scheme not in ("http", "https"):
                    scheme = "http"
                origin = f"{scheme}://{host}/maps"
            # Keep HEAD support limited to downloadable packages.
            if head_only and not re.fullmatch(r"/v1/offline/regions/[a-z-]+/download", path):
                self.send_response(405)
                self.end_headers()
                return
            if path == "/v1/offline/catalog":
                return self.send_json({"schema": "vexa.offline.catalog.v1", "regions":
                                       catalog(store.offline_directory, origin, store.offline_downloads)})
            offline_match = re.fullmatch(r"/v1/offline/regions/([a-z-]+)/(manifest|download)", path)
            if offline_match:
                region_id, action = offline_match.groups()
                if region_id not in REGIONS:
                    return self.send_json({"error": "Неизвестный округ"}, 404)
                manifest = (read_manifest(store.offline_directory, region_id)
                            if store.offline_directory else None)
                if manifest is None:
                    return self.send_json({"error": "Региональный пакет не опубликован"}, 404)
                if action == "manifest":
                    return self.send_json(manifest)
                if not store.offline_downloads:
                    return self.send_json({"error": "Скачивание пакетов отключено администратором"}, 403)
                return self.send_offline_file(region_id, manifest, head_only)
            if path in ("/", "/health"):
                return self.send_json({"service": "VEXA MAP", "version": "0.3.19", "map_ready": store.map_ready,
                                       "search_ready": store.search_ready, "routing_configured": bool(store.osrm_url),
                                       "tile_format": store.format or None, "package_count": store.package_count,
                                       "vector_style_required": store.vector_only and not store.map_ready,
                                       "vector_labels_available": store.vector_labels,
                                       "offline_available": sum(r["available"] for r in catalog(store.offline_directory)),
                                       "offline_downloads_enabled": store.offline_downloads})
            if path in ("/style.json", "/styles/vexa/style.json"):
                # Only Driver's explicit 3D mode requests volume extrusions. Client is always 2D.
                if store.vector_only and store.map_ready:
                    return self.send_json(store.vector_style(origin, buildings3d=params.get('view') == ['3d']))
                if store.map_ready and store.format != "pbf":
                    sources = {"vexa": {"type": "raster", "tiles": [f"{origin}/tiles/{{z}}/{{x}}/{{y}}.{store.format}"],
                                         "tileSize": 256, "minzoom": store.minzoom, "maxzoom": store.maxzoom,
                                         "attribution": store.attribution}}
                    layers = [{"id": "background", "type": "background", "paint": {"background-color": "#151D21"}},
                              {"id": "vexa-raster", "type": "raster", "source": "vexa"}]
                else:
                    # No fictitious map! Background only; readiness is visible via /health.
                    sources = {}
                    layers = [{"id": "background", "type": "background", "paint": {"background-color": "#151D21"}}]
                return self.send_json({"version": 8, "name": "VEXA MAP", "center": [37.618423, 55.751244],
                                       "zoom": 11, "sources": sources, "layers": layers})
            if path == "/tilejson.json":
                if not store.map_ready:
                    return self.send_json({"error": "Растровый пакет не установлен или требуется векторный стиль"}, 503)
                return self.send_json({"tilejson": "3.0.0", "name": "VEXA MAP", "format": store.format,
                                       "minzoom": store.minzoom, "maxzoom": store.maxzoom,
                                       "tiles": [f"{origin}/tiles/{{z}}/{{x}}/{{y}}.{store.format}"],
                                       "attribution": store.attribution})
            glyph_match = re.fullmatch(r'/glyphs/([^/]{1,100})/(\d{1,5})-(\d{1,5})\.pbf', path)
            if glyph_match:
                from urllib.parse import unquote
                fontstack = unquote(glyph_match[1])
                start, end = int(glyph_match[2]), int(glyph_match[3])
                if end != start + 255 or start > 65280 or start % 256:
                    return self.send_json({'error': 'Недопустимый диапазон глифов'}, 400)
                data = store.glyph(fontstack, start)
                if data is None:
                    return self.send_json({'error': 'Локальные глифы отсутствуют'}, 404)
                if data[:2] == b'\x1f\x8b':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/x-protobuf')
                    self.send_header('Content-Encoding', 'gzip')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    return self.wfile.write(data)
                return self.send_bytes(data, 'application/x-protobuf', cache_seconds=3600)
            if path.startswith("/tiles/"):
                sections = path.removeprefix("/tiles/").split("/")
                if len(sections) != 3 or not sections[-1].count(".") == 1:
                    return self.send_json({"error": "Неверный путь тайла"}, 400)
                try:
                    z, x = map(int, sections[:2])
                    ystr, ext = sections[-1].rsplit(".", 1)
                    y = int(ystr)
                except ValueError:
                    return self.send_json({"error": "Неверные координаты тайла"}, 400)
                if ext.lower() != store.format or not store.map_ready:
                    return self.send_json({"error": "Формат тайла или пакет недоступен"}, 404)
                tile = store.tile(z, x, y)
                if tile is None:
                    return self.send_json({"error": "Тайл отсутствует в пакете"}, 404)
                if store.format == "pbf" and tile[:2] == b"\x1f\x8b":
                    self.send_response(200)
                    self.send_header("Content-Type", store.tile_mime)
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Length", str(len(tile)))
                    self.send_header("Cache-Control", "public, max-age=3600")
                    self.end_headers()
                    return self.wfile.write(tile)
                return self.send_bytes(tile, store.tile_mime, cache_seconds=3600)
            if path in ("/v1/search", "/api/v1/search"):
                try:
                    return self.send_json({"results": store.search(params.get("q", [""])[0])})
                except RuntimeError as exc:
                    return self.send_json({"error": str(exc)}, 503)
            if path in ("/v1/route", "/api/v1/route"):
                try:
                    vals = [float(params[x][0]) for x in ("start_lat", "start_lon", "end_lat", "end_lon")]
                    return self.send_json(store.route(*vals))
                except (ValueError, KeyError, IndexError):
                    return self.send_json({"error": "Укажите корректные start_lat, start_lon, end_lat, end_lon"}, 400)
                except (HTTPError, URLError, TimeoutError, OSError, RuntimeError, json.JSONDecodeError) as exc:
                    return self.send_json({"error": f"Локальный маршрутизатор недоступен: {exc}"}, 503)
            return self.send_json({"error": "Не найдено"}, 404)
    return Handler


def import_places(csv_path: Path, database: Path):
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database)) as db:
        db.execute("CREATE TABLE IF NOT EXISTS places (name TEXT NOT NULL, name_search TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL)")
        db.execute("CREATE INDEX IF NOT EXISTS ix_places_name_search ON places(name_search)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_places_unique ON places(name, latitude, longitude)")
        with csv_path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if not {"name", "latitude", "longitude"}.issubset(reader.fieldnames or []):
                raise ValueError("CSV must have name,latitude,longitude columns")
            for row in reader:
                try:
                    lat, lon = float(row["latitude"]), float(row["longitude"])
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or not row["name"].strip():
                        continue
                    db.execute("INSERT OR IGNORE INTO places(name, name_search, latitude, longitude) VALUES (?, ?, ?, ?)", (row["name"].strip(), row["name"].strip().casefold(), lat, lon))
                except (TypeError, ValueError):
                    continue
        db.commit()


def main():
    parser = argparse.ArgumentParser(description="Local VEXA MAP service")
    parser.add_argument("--host", default=os.getenv("VEXA_MAP_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("VEXA_MAP_PORT", "8090")))
    parser.add_argument("--mbtiles", default=os.getenv("VEXA_MAP_MBTILES", ""))
    parser.add_argument("--places", default=os.getenv("VEXA_MAP_PLACES", ""))
    parser.add_argument("--osrm", default=os.getenv("VEXA_MAP_OSRM_URL", ""))
    parser.add_argument("--public-base", default=os.getenv("VEXA_MAP_PUBLIC_BASE", ""))
    parser.add_argument("--trust-proxy", action="store_true", default=os.getenv("VEXA_MAP_TRUST_PROXY") == "1")
    parser.add_argument("--import-places", metavar="CSV")
    parser.add_argument("--publish-region", choices=tuple(REGIONS),
                        help="Generate manifest and SHA256 for a <region>.mbtiles file")
    parser.add_argument("--data-version", default="", help="Required with --publish-region")
    parser.add_argument("--verify-region", choices=tuple(REGIONS),
                        help="Check SHA256 of a published region file (can take time)")
    parser.add_argument("--serve-offline-packs", action="store_true",
                        default=os.getenv("VEXA_MAP_SERVE_OFFLINE_PACKS", "0") == "1",
                        help="Allow unauthenticated downloads (private network only)")
    args = parser.parse_args()
    if args.import_places:
        if not args.places:
            parser.error("Set --places to the destination SQLite file")
        import_places(Path(args.import_places), Path(args.places))
        print(f"Адресный индекс обновлён: {args.places}")
        return
    if args.publish_region or args.verify_region:
        region_dir = Path(args.mbtiles)
        if not args.mbtiles or not region_dir.is_dir():
            parser.error("Set --mbtiles to a directory containing regional packs")
        if args.publish_region:
            if not args.data_version:
                parser.error("--data-version is required with --publish-region")
            print(json.dumps(publish_region(region_dir, args.publish_region, args.data_version),
                             ensure_ascii=False, indent=2))
            return
        if not verify_region(region_dir, args.verify_region):
            parser.exit(1, "Ошибка: контрольная сумма не совпала или пакет отсутствует\n")
        print(f"Контрольная сумма {args.verify_region} верна")
        return
    store = MapStore(args.mbtiles, args.places, args.osrm, args.serve_offline_packs)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(store, args.public_base, args.trust_proxy))
    print(f"VEXA MAP listening on http://{args.host}:{args.port}, tiles={store.map_ready}, search={store.search_ready}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
