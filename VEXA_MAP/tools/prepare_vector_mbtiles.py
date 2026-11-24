#!/usr/bin/env python3
"""Validate an operator-provided vector MBTiles and optionally embed licensed MapLibre glyph PBF ranges.

Does not download, generate, or redistribute font files. Provide SDF glyph range files
created from fonts with a licence suitable for the intended deployment.
Run BEFORE SHA-256 publication of the district. Changes are transactional.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sqlite3

REGIONS = ('central', 'northwestern', 'southern', 'north-caucasus', 'volga', 'ural', 'siberian', 'far-eastern')
FONTSTACK = 'Noto Sans Regular'
REQUIRED_RANGES = (0, 256, 1024)  # Basic Latin, extended Latin, basic Cyrillic (256 glyphs per range)


def check_tiles(db: sqlite3.Connection) -> tuple[dict, list[str]]:
    meta = dict(db.execute('SELECT name,value FROM metadata'))
    if meta.get('format', '').lower() != 'pbf':
        raise ValueError('An MBTiles with metadata.format=pbf is required')
    try:
        layers = json.loads(meta.get('json', '{}'))['vector_layers']
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError('metadata.json with vector_layers is required') from exc
    ids = [entry.get('id') for entry in layers if isinstance(entry, dict)]
    if not ids or not all(isinstance(i, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', i) for i in ids):
        raise ValueError('Invalid/empty vector_layers in metadata.json')
    # The style adapts to optional transportation_name / building / water / place layers.
    if not {'transportation', 'road'}.intersection(ids):
        raise ValueError('Vector tiles must have transportation or road source-layer for road display')
    if db.execute('SELECT 1 FROM tiles LIMIT 1').fetchone() is None:
        raise ValueError('Empty vector MBTiles: no tiles')
    return meta, ids


def prepare(mbtiles: Path, region: str, glyphs_dir: Path | None = None) -> dict:
    if region not in REGIONS:
        raise ValueError('Unknown federal district')
    if not mbtiles.is_file():
        raise FileNotFoundError(mbtiles)
    assets: dict[int, bytes] = {}
    if glyphs_dir is not None:
        folder = glyphs_dir / FONTSTACK
        if not folder.is_dir():
            raise ValueError(f'Missing fontstack directory: {folder}')
        for path in folder.iterdir():
            m = re.fullmatch(r'(\d{1,5})-(\d{1,5})\.pbf', path.name)
            if not m:
                continue
            start, end = map(int, m.groups())
            if start % 256 or start > 65280 or end != start + 255:
                raise ValueError(f'Invalid glyph range: {path.name}')
            if not path.is_file() or not 0 < path.stat().st_size <= 2 * 1024 * 1024:
                raise ValueError(f'Empty/oversized glyph file: {path.name}')
            assets[start] = path.read_bytes()
        if not set(REQUIRED_RANGES).issubset(assets):
            raise ValueError('Glyphs missing required ranges: 0-255, 256-511, 1024-1279')
    with sqlite3.connect(mbtiles) as db:
        metadata, layers = check_tiles(db)
        db.execute('BEGIN IMMEDIATE')
        try:
            # Never erase existing symbols if only validating a package.
            if glyphs_dir is not None:
                db.execute('CREATE TABLE IF NOT EXISTS vexa_glyphs('
                           'fontstack TEXT NOT NULL, range_start INTEGER NOT NULL, pbf BLOB NOT NULL, '
                           'PRIMARY KEY(fontstack,range_start)) WITHOUT ROWID')
                db.execute('DELETE FROM vexa_glyphs WHERE fontstack=?', (FONTSTACK,))
                db.executemany('INSERT INTO vexa_glyphs VALUES(?,?,?)',
                               ((FONTSTACK, start, payload) for start, payload in sorted(assets.items())))
            db.execute('DELETE FROM metadata WHERE name=?', ('vexa_region_id',))
            db.execute('INSERT INTO metadata(name,value) VALUES(?,?)', ('vexa_region_id', region))
            db.commit()
        except BaseException:
            db.rollback()
            raise
    return {'region': region, 'vector_layers': layers, 'embedded_fontstack': FONTSTACK if assets else None,
            'glyph_ranges': len(assets), 'has_road_layer': True,
            'has_3d_buildings': 'building' in layers,
            'has_place_labels': 'place' in layers,
            'note': 'Republish SHA-256 manifest after embedding glyphs'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mbtiles', type=Path, required=True)
    parser.add_argument('--region', choices=REGIONS, required=True)
    parser.add_argument('--glyphs-dir', type=Path, help='Directory containing licensed Noto Sans Regular/<start>-<end>.pbf glyph ranges')
    args = parser.parse_args()
    print(json.dumps(prepare(args.mbtiles, args.region, args.glyphs_dir), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
