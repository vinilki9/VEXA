#!/usr/bin/env python3
"""Embed licensed regional addresses + directed road graph in an *existing* MBTiles.

CSV inputs MUST be produced from licensed address and road datasets by an operator.
The tool modifies the MBTiles IN PLACE, before generating its public SHA-256 manifest.
No sample places or road geometry are silently added to production data.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata

REGIONS = ('central', 'northwestern', 'southern', 'north-caucasus',
           'volga', 'ural', 'siberian', 'far-eastern')


def tokens(value: str) -> list[str]:
    return [w for w in re.split(r'[_\W]+', value.casefold().replace('ё', 'е')) if w][:32]


def check_geo(lat: str, lon: str) -> tuple[float, float]:
    a, b = float(lat), float(lon)
    if not (math.isfinite(a) and math.isfinite(b) and -90 <= a <= 90 and -180 <= b <= 180):
        raise ValueError('invalid latitude/longitude')
    return a, b


def rows(path: Path, columns: set[str]):
    with path.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if not columns.issubset(reader.fieldnames or []):
            raise ValueError(f'{path.name} needs CSV columns {sorted(columns)}')
        for row in reader:
            yield row


def install(mbtiles: Path, region: str, places: Path, nodes: Path, edges: Path, turns: Path | None = None) -> dict:
    if region not in REGIONS:
        raise ValueError('unknown federal district')
    if not mbtiles.is_file() or mbtiles.suffix != '.mbtiles':
        raise ValueError('existing MBTiles required')
    for path in (places, nodes, edges):
        if not path.is_file():
            raise ValueError(f'missing input: {path}')
    # All changes (including metadata) are transactional. Build before publishing SHA-256.
    with sqlite3.connect(str(mbtiles)) as db:
        db.execute('PRAGMA foreign_keys = ON')
        db.execute('PRAGMA busy_timeout = 30000')
        if db.execute("SELECT name FROM sqlite_master WHERE name='tiles'").fetchone() is None:
            raise ValueError('MBTiles tiles table/view missing')
        if db.execute("SELECT name FROM sqlite_master WHERE name='metadata'").fetchone() is None:
            raise ValueError('MBTiles metadata missing')
        db.execute('BEGIN IMMEDIATE')
        try:
            # Rebuild navigation tables on upgrade; old raster tiles remain untouched.
            for table in ('vexa_turn_restrictions', 'vexa_node_rtree', 'vexa_terms', 'vexa_edges', 'vexa_places', 'vexa_nodes'):
                db.execute(f'DROP TABLE IF EXISTS {table}')
            db.execute('CREATE TABLE vexa_places(place_id INTEGER PRIMARY KEY, name TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL, rank INTEGER NOT NULL)')
            db.execute('CREATE TABLE vexa_terms(term TEXT NOT NULL, place_id INTEGER NOT NULL, PRIMARY KEY(term, place_id)) WITHOUT ROWID')
            db.execute('CREATE TABLE vexa_nodes(node_id INTEGER PRIMARY KEY, latitude REAL NOT NULL, longitude REAL NOT NULL)')
            db.execute('CREATE TABLE vexa_edges(source_id INTEGER NOT NULL, target_id INTEGER NOT NULL, distance_m REAL NOT NULL CHECK(distance_m>0), duration_s REAL NOT NULL CHECK(duration_s>0))')
            db.execute('CREATE TABLE vexa_turn_restrictions(from_id INTEGER NOT NULL, via_id INTEGER NOT NULL, to_id INTEGER NOT NULL, PRIMARY KEY(from_id,via_id,to_id)) WITHOUT ROWID')
            n_places = n_nodes = n_edges = n_turns = 0
            for row in rows(places, {'name', 'latitude', 'longitude'}):
                name = row['name'].strip()
                lat, lon = check_geo(row['latitude'], row['longitude'])
                if not name or len(name) > 350:
                    raise ValueError('empty/long address name')
                n_places += 1
                rank = int(row.get('rank') or 0)
                db.execute('INSERT INTO vexa_places VALUES(?,?,?,?,?)', (n_places, name, lat, lon, rank))
                db.executemany('INSERT INTO vexa_terms VALUES(?,?)', ((t, n_places) for t in set(tokens(name))))
            for row in rows(nodes, {'node_id', 'latitude', 'longitude'}):
                lat, lon = check_geo(row['latitude'], row['longitude'])
                db.execute('INSERT INTO vexa_nodes VALUES(?,?,?)', (int(row['node_id']), lat, lon))
                n_nodes += 1
            for row in rows(edges, {'source_id', 'target_id', 'distance_m', 'duration_s'}):
                a, b = int(row['source_id']), int(row['target_id'])
                metres, seconds = float(row['distance_m']), float(row['duration_s'])
                if a == b or not (math.isfinite(metres) and math.isfinite(seconds) and metres > 0 and seconds > 0):
                    raise ValueError('invalid directed road edge')
                db.execute('INSERT INTO vexa_edges VALUES(?,?,?,?)', (a, b, metres, seconds))
                n_edges += 1
            if turns is not None:
                if not turns.is_file():
                    raise ValueError(f'missing input: {turns}')
                for row in rows(turns, {'from_id', 'via_id', 'to_id'}):
                    a, b, c = int(row['from_id']), int(row['via_id']), int(row['to_id'])
                    db.execute('INSERT INTO vexa_turn_restrictions VALUES(?,?,?)', (a,b,c))
                    n_turns += 1
                if db.execute('''SELECT 1 FROM vexa_turn_restrictions t
                    WHERE NOT EXISTS (SELECT 1 FROM vexa_edges e WHERE e.source_id=t.from_id AND e.target_id=t.via_id)
                       OR NOT EXISTS (SELECT 1 FROM vexa_edges e WHERE e.source_id=t.via_id AND e.target_id=t.to_id)
                    LIMIT 1''').fetchone():
                    raise ValueError('turn restriction references non-existing directed arc')
            if n_places < 1 or n_nodes < 2 or n_edges < 1:
                raise ValueError('empty place index or road graph')
            if db.execute('SELECT 1 FROM vexa_edges e LEFT JOIN vexa_nodes a ON a.node_id=e.source_id LEFT JOIN vexa_nodes b ON b.node_id=e.target_id WHERE a.node_id IS NULL OR b.node_id IS NULL LIMIT 1').fetchone():
                raise ValueError('road edge references missing node')
            # Optional spatial acceleration. A full graph is still not loaded into RAM.
            db.execute('CREATE VIRTUAL TABLE vexa_node_rtree USING rtree(node_id,min_lat,max_lat,min_lon,max_lon)')
            db.execute('INSERT INTO vexa_node_rtree SELECT node_id,latitude,latitude,longitude,longitude FROM vexa_nodes')
            db.execute('CREATE INDEX vexa_nodes_lat_lon_idx ON vexa_nodes(latitude,longitude)')
            db.execute('CREATE INDEX vexa_edges_source_idx ON vexa_edges(source_id)')
            for key, value in [('vexa_navigation_schema', 'v2' if turns is not None else 'v1'), ('vexa_region_id', region)]:
                db.execute('DELETE FROM metadata WHERE name=?', (key,))
                db.execute('INSERT INTO metadata(name,value) VALUES(?,?)', (key, value))
            db.commit()
        except BaseException:
            db.rollback()
            raise
    return {'region': region, 'places': n_places, 'nodes': n_nodes, 'directed_edges': n_edges, 'forbidden_turns': n_turns}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mbtiles', type=Path, required=True)
    p.add_argument('--region', choices=REGIONS, required=True)
    p.add_argument('--places', type=Path, required=True, help='CSV name,latitude,longitude,rank')
    p.add_argument('--nodes', type=Path, required=True, help='CSV node_id,latitude,longitude')
    p.add_argument('--edges', type=Path, required=True, help='CSV source_id,target_id,distance_m,duration_s (one directed arc per row)')
    p.add_argument('--turns', type=Path, help='Optional CSV from_id,via_id,to_id (forbidden transitions)')
    a = p.parse_args()
    print(install(a.mbtiles, a.region, a.places, a.nodes, a.edges, a.turns))


if __name__ == '__main__':
    main()
