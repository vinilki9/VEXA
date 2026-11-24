#!/usr/bin/env python3
"""Read-only validation of a VEXA navigation MBTiles graph (schema v1).

Does not assert that legal turn restrictions or road levels exist in v1.
"""
import argparse
import json
import sqlite3
from pathlib import Path

REQUIRED = {'vexa_nodes', 'vexa_edges', 'metadata'}

def audit(path: Path, expected_region: str | None = None) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    # SQLite read-only URI: never create or modify an input map.
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = REQUIRED - tables
        if missing:
            raise ValueError(f'missing tables: {sorted(missing)}')
        metadata = dict(db.execute("SELECT name,value FROM metadata WHERE name IN ('vexa_navigation_schema','vexa_region_id')"))
        nodes = db.execute('SELECT COUNT(*) FROM vexa_nodes').fetchone()[0]
        edges = db.execute('SELECT COUNT(*) FROM vexa_edges').fetchone()[0]
        bad_refs = db.execute('''SELECT COUNT(*) FROM vexa_edges e
            LEFT JOIN vexa_nodes a ON a.node_id=e.source_id
            LEFT JOIN vexa_nodes b ON b.node_id=e.target_id
            WHERE a.node_id IS NULL OR b.node_id IS NULL''').fetchone()[0]
        bad_weights = db.execute('''SELECT COUNT(*) FROM vexa_edges
            WHERE distance_m <= 0 OR duration_s <= 0 OR distance_m IS NULL OR duration_s IS NULL
               OR distance_m > 1e12 OR duration_s > 1e12''').fetchone()[0]
        isolated = db.execute('''SELECT COUNT(*) FROM vexa_nodes n WHERE NOT EXISTS
            (SELECT 1 FROM vexa_edges e WHERE e.source_id=n.node_id OR e.target_id=n.node_id)''').fetchone()[0]
        bounds = db.execute('SELECT MIN(latitude),MAX(latitude),MIN(longitude),MAX(longitude) FROM vexa_nodes').fetchone()
        bad_coordinates = db.execute('''SELECT COUNT(*) FROM vexa_nodes WHERE latitude NOT BETWEEN -90 AND 90
            OR longitude NOT BETWEEN -180 AND 180 OR latitude IS NULL OR longitude IS NULL''').fetchone()[0]
        rtree_present = 'vexa_node_rtree' in tables
        rtree_count = None
        if rtree_present:
            rtree_count = db.execute('SELECT COUNT(*) FROM vexa_node_rtree').fetchone()[0]
        errors = []
        if rtree_present and rtree_count != nodes: errors.append('spatial index node count mismatch')
        if metadata.get('vexa_navigation_schema') != 'v1': errors.append('unsupported navigation schema')
        if expected_region and metadata.get('vexa_region_id') != expected_region: errors.append('region mismatch')
        if nodes < 2 or edges < 1: errors.append('empty graph')
        if bad_refs: errors.append('edges referencing missing nodes')
        if bad_weights: errors.append('invalid edge weights')
        if bad_coordinates: errors.append('invalid coordinates')
        return {'ok': not errors, 'errors': errors, 'region': metadata.get('vexa_region_id'),
                'nodes': nodes, 'directed_edges': edges, 'isolated_nodes': isolated,
                'spatial_index': 'rtree' if rtree_present else 'legacy_btree',
                'bounds_lat_lon': bounds, 'note': 'v1 has no turn restrictions, lane geometry or elevation; these cannot be validated'}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mbtiles', type=Path)
    p.add_argument('--region', default=None)
    args = p.parse_args()
    try:
        result = audit(args.mbtiles, args.region)
    except (OSError, ValueError, sqlite3.DatabaseError) as exc:
        result = {'ok': False, 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ok'] else 1)

if __name__ == '__main__': main()
