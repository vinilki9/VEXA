"""Manifest generation and validation for VEXA MAP district MBTiles downloads.

This module does NOT render a tile, create a road graph or license datasets.
A package must be built from legally distributable MBTiles and explicitly
published by a trusted operator.  SHA-256 protects against accidental corruption,
not a malicious replacement of both the package and its manifest.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

SCHEMA = "vexa.offline.region.v1"
REGIONS = {
    "central": "Центральный федеральный округ",
    "northwestern": "Северо-Западный федеральный округ",
    "southern": "Южный федеральный округ",
    "north-caucasus": "Северо-Кавказский федеральный округ",
    "volga": "Приволжский федеральный округ",
    "ural": "Уральский федеральный округ",
    "siberian": "Сибирский федеральный округ",
    "far-eastern": "Дальневосточный федеральный округ",
}
SUPPORTED_FORMATS = {"png", "jpg", "webp", "pbf"}
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MAX_ZOOM = 22


def hash_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(4 * 1024 * 1024):
            sha.update(block)
    return sha.hexdigest()


def mbtiles_info(path: Path) -> dict:
    if not path.is_file() or path.suffix != ".mbtiles":
        raise ValueError("Нужен существующий MBTiles файл")
    # mode=ro prevents accidental mutation of the source.
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        meta = dict(db.execute("SELECT name, value FROM metadata"))
        if db.execute("SELECT 1 FROM tiles LIMIT 1").fetchone() is None:
            raise ValueError("Нельзя публиковать пустой MBTiles")
    fmt = str(meta.get("format", "")).lower()
    if fmt == "jpeg":
        fmt = "jpg"
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError("Формат MBTiles не поддерживается")
    minzoom = int(meta.get("minzoom", 0))
    maxzoom = int(meta.get("maxzoom", 18))
    if not (0 <= minzoom <= maxzoom <= MAX_ZOOM):
        raise ValueError("Недопустимый диапазон масштабов")
    return {"format": fmt, "minzoom": minzoom, "maxzoom": maxzoom,
            "attribution": str(meta.get("attribution", ""))}


def publish_region(directory: Path, region_id: str, version: str) -> dict:
    """Publish a manifest adjacent to <region_id>.mbtiles, atomically."""
    if region_id not in REGIONS:
        raise ValueError("Неизвестный федеральный округ")
    if not VERSION_RE.fullmatch(version):
        raise ValueError("Версия должна состоять из букв, цифр, '.', '-' или '_'")
    directory = directory.resolve()
    pack = directory / f"{region_id}.mbtiles"
    info = mbtiles_info(pack)
    manifest = {
        "schema": SCHEMA,
        "region_id": region_id,
        "region_name": REGIONS[region_id],
        "data_version": version,
        "file_name": pack.name,
        "size_bytes": pack.stat().st_size,
        "sha256": hash_file(pack),
        "format": info["format"],
        "minzoom": info["minzoom"],
        "maxzoom": info["maxzoom"],
        "attribution": info["attribution"],
        "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    final = directory / f"{region_id}.manifest.json"
    temp = directory / f"{region_id}.manifest.json.tmp"
    temp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(final)
    return manifest


def read_manifest(directory: Path, region_id: str) -> dict | None:
    """Validate metadata without scanning huge packages; clients verify SHA-256."""
    if region_id not in REGIONS:
        return None
    directory = directory.resolve()
    path = directory / f"{region_id}.manifest.json"
    file = directory / f"{region_id}.mbtiles"
    if not path.is_file() or not file.is_file() or path.is_symlink() or file.is_symlink():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        if not (data.get("schema") == SCHEMA and data.get("region_id") == region_id
                and data.get("region_name") == REGIONS[region_id]
                and data.get("file_name") == file.name
                and isinstance(data.get("size_bytes"), int)
                and not isinstance(data.get("size_bytes"), bool)
                and data["size_bytes"] > 0
                and file.stat().st_size == data["size_bytes"]
                and isinstance(data.get("sha256"), str)
                and DIGEST_RE.fullmatch(data["sha256"])
                and isinstance(data.get("data_version"), str)
                and VERSION_RE.fullmatch(data["data_version"])
                and data.get("format") in SUPPORTED_FORMATS
                and type(data.get("minzoom")) is int and type(data.get("maxzoom")) is int
                and 0 <= data["minzoom"] <= data["maxzoom"] <= MAX_ZOOM):
            return None
        return data
    except (ValueError, OSError, TypeError, json.JSONDecodeError):
        return None


def verify_region(directory: Path, region_id: str) -> bool:
    """Full on-disk digest verification; intentionally an operator-side operation."""
    manifest = read_manifest(directory, region_id)
    if manifest is None:
        return False
    file = directory.resolve() / manifest["file_name"]
    return hash_file(file) == manifest["sha256"]


def catalog(directory: Path | None, origin: str = "", downloadable: bool = False) -> list[dict]:
    result = []
    for region_id, name in REGIONS.items():
        manifest = read_manifest(directory, region_id) if directory else None
        row = {"region_id": region_id, "region_name": name,
               "available": manifest is not None}
        if manifest:
            row.update({key: manifest[key] for key in
                        ("data_version", "size_bytes", "sha256", "format", "minzoom", "maxzoom")})
            if downloadable:
                row["manifest_url"] = f"{origin}/v1/offline/regions/{region_id}/manifest"
                row["download_url"] = f"{origin}/v1/offline/regions/{region_id}/download"
        result.append(row)
    return result
