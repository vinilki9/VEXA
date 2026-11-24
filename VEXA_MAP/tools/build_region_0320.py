#!/usr/bin/env python3
"""VEXA MAP: plan and explicitly build ONE real Geofabrik OSM district extract.

No downloads, no server changes, no silent deletion/replacement. The input PBF and
external Tilemaker/OSRM binaries must be supplied by the operator. Results are
staged then promoted to a *versioned local build folder*, never installed to an
Android device or published to the VEXA API automatically.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from prepare_vector_mbtiles import prepare

GIB = 1024 ** 3
REGIONS = {
    'central': 'central-fed-district',
    'northwestern': 'northwestern-fed-district',
    'southern': 'south-fed-district',
    'north-caucasus': 'north-caucasus-fed-district',
    'volga': 'volga-fed-district',
    'ural': 'ural-fed-district',
    'siberian': 'siberian-fed-district',
    'far-eastern': 'far-eastern-fed-district',
}
VERSION_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z')
SHA_RE = re.compile(r'[0-9a-fA-F]{64}\Z')


def source_url(region: str) -> str:
    slug = REGIONS[region]
    return f'https://download.geofabrik.de/russia/{slug}-latest.osm.pbf'


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def directory_bytes(directory: Path) -> int:
    if not directory.exists():
        return 0
    total = 0
    for dirpath, _, files in os.walk(directory, followlinks=False):
        for file in files:
            p = Path(dirpath) / file
            if not p.is_symlink():
                try:
                    total += p.stat().st_size
                except FileNotFoundError:
                    continue
    return total


def disk_projection(source_bytes: int, routing: bool) -> int:
    """Conservative planning heuristic, NOT a hard maximum or measured forecast."""
    return max(source_bytes * (24 if routing else 12), 2 * GIB if routing else GIB)


def steps(pbf: Path, stage: Path, config: Path, process: Path,
          profile: Path | None, tilemaker: str = 'tilemaker',
          osrm_prefix: str = '') -> list[tuple[str, list[str]]]:
    vector = [tilemaker, '--input', str(pbf), '--output', str(stage / 'map.mbtiles'),
              '--config', str(config), '--process', str(process),
              '--store', str(stage / 'tilemaker-store')]
    items = [('vector', vector)]
    if profile:
        route = stage / 'osrm' / 'region.osm.pbf'
        base = stage / 'osrm' / 'region.osrm'
        items.extend([
            ('routing-extract', [osrm_prefix + 'osrm-extract', '-p', str(profile), str(route)]),
            ('routing-partition', [osrm_prefix + 'osrm-partition', str(base)]),
            ('routing-customize', [osrm_prefix + 'osrm-customize', str(base)]),
        ])
    return items


def ensure_source(pbf: Path) -> None:
    if not pbf.is_file() or not pbf.name.endswith('.osm.pbf') or pbf.stat().st_size == 0:
        raise ValueError('Укажите непустой реальный входной .osm.pbf файл')
    if pbf.is_symlink():
        raise ValueError('Символьные ссылки в качестве OSM-источника не допускаются')


def validate_params(region: str, version: str, budget_gib: int, reserve_gib: int) -> None:
    if region not in REGIONS:
        raise ValueError('Неизвестный федеральный округ')
    if not VERSION_RE.fullmatch(version):
        raise ValueError('Некорректная версия сборки')
    if not (1 <= budget_gib <= 250) or not (0 <= reserve_gib < budget_gib):
        raise ValueError('Бюджет диска: 1–250 ГиБ, резерв должен быть меньше бюджета')


def build_plan(region: str, version: str, pbf: Path, output: Path,
               config: Path, process: Path, profile: Path | None,
               budget_gib: int = 250, reserve_gib: int = 15,
               tilemaker: str = 'tilemaker', osrm_prefix: str = '') -> dict:
    validate_params(region, version, budget_gib, reserve_gib)
    pbf = pbf.expanduser().resolve()
    output = output.expanduser().resolve()
    config = config.expanduser().resolve()
    process = process.expanduser().resolve()
    profile = profile.expanduser().resolve() if profile else None
    dest = output / f'{region}-{version}'
    staging = output / f'.{region}-{version}.pending'
    source_bytes = pbf.stat().st_size if pbf.is_file() else 0
    expected = disk_projection(source_bytes, profile is not None)
    parts = steps(pbf, staging, config, process, profile, tilemaker, osrm_prefix)
    missing_tools = sorted({cmd[0] for _, cmd in parts if shutil.which(cmd[0]) is None})
    # Plan mode does not create folders, download datasets, or run external processes.
    anchor = output if output.exists() else next((v for v in (output, *output.parents) if v.exists()), Path.cwd())
    available = shutil.disk_usage(anchor).free
    existing_workspace_bytes = directory_bytes(output)
    return {
        'region_id': region, 'geofabrik_extract_url': source_url(region),
        'input_pbf': str(pbf), 'input_exists': bool(source_bytes),
        'source_bytes': source_bytes, 'version': version,
        'existing_workspace_bytes': existing_workspace_bytes,
        'estimated_extra_bytes': expected, 'estimated_not_guaranteed': True,
        'workspace_budget_gib': budget_gib, 'reserve_gib': reserve_gib,
        'available_bytes': available, 'output': str(dest), 'staging': str(staging),
        'route_graph_requested': profile is not None,
        'commands': [{'step': name, 'argv': cmd} for name, cmd in parts],
        'missing_tools': missing_tools,
        'ready_for_execution': all([source_bytes, not missing_tools, config.is_file(), process.is_file(),
                                    profile is None or profile.is_file(),
                                    expected + reserve_gib * GIB <= available,
                                    expected + reserve_gib * GIB + existing_workspace_bytes <= budget_gib * GIB,
                                    not dest.exists(), not staging.exists()]),
    }


def monitored_run(name: str, argv: list[str], stage: Path, *,
                  base_usage: int, limit: int, reserve: int, output: Path) -> None:
    log = stage / f'{name}.log'
    with log.open('wb') as stream:
        process = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                # The process may create large temporary datasets during a single stage.
                if base_usage + directory_bytes(stage) > limit or shutil.disk_usage(output).free < reserve:
                    process.terminate()
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    raise RuntimeError(f'{name}: остановлено из-за лимита диска; см. {log}')
                time.sleep(1)
            if process.returncode != 0:
                raise RuntimeError(f'{name}: код завершения {process.returncode}; см. {log}')
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()


def execute_plan(plan: dict, *, expected_sha256: str | None = None,
                 glyphs_dir: Path | None = None) -> dict:
    """Run only after explicit --execute; never alters previously released packs."""
    if plan['missing_tools']:
        raise ValueError('Установите внешние инструменты: ' + ', '.join(plan['missing_tools']))
    if not plan['ready_for_execution']:
        raise ValueError('Preflight не пройден: проверьте входные файлы, свободное место и имя сборки')
    if expected_sha256 and not SHA_RE.fullmatch(expected_sha256):
        raise ValueError('Ожидаемая SHA-256 должна содержать 64 шестнадцатеричных символа')
    pbf = Path(plan['input_pbf'])
    ensure_source(pbf)
    source_hash = sha256(pbf)
    if expected_sha256 and source_hash.lower() != expected_sha256.lower():
        raise ValueError('SHA-256 входного OSM-файла не совпадает с ожидаемой')
    output = Path(plan['output']).parent
    stage = Path(plan['staging'])
    dest = Path(plan['output'])
    # Refuse symlinked output roots to prevent unexpected writes outside workspace.
    if output.exists() and output.is_symlink():
        raise ValueError('Нельзя использовать ссылку вместо каталога сборки')
    output.mkdir(parents=True, exist_ok=True)
    if dest.exists() or stage.exists():
        raise FileExistsError('Версия уже существует, существующая сборка не перезаписывается')
    base_usage = directory_bytes(output)
    stage.mkdir()
    # Tilemaker creates its on-disk store directory when it starts.
    if plan['route_graph_requested']:
        route = stage / 'osrm'
        route.mkdir()
        shutil.copyfile(pbf, route / 'region.osm.pbf')
    try:
        for part in plan['commands']:
            monitored_run(part['step'], part['argv'], stage,
                          base_usage=base_usage,
                          limit=plan['workspace_budget_gib'] * GIB,
                          reserve=plan['reserve_gib'] * GIB, output=output)
        # Never publish a fake MBTiles; validator insists on nonempty PBF tiles.
        result = prepare(stage / 'map.mbtiles', plan['region_id'], glyphs_dir)
        if result['has_road_layer'] is not True:
            raise ValueError('Отсутствует слой дорог')
        if plan['route_graph_requested'] and not (stage / 'osrm' / 'region.osrm').is_file():
            raise ValueError('OSRM не создал region.osrm; граф отсутствует')
        receipt = {
            'schema': 'vexa.map.build.v1', 'region_id': plan['region_id'],
            'version': plan['version'], 'built_at': datetime.now(timezone.utc).isoformat(),
            'suggested_geofabrik_url': plan['geofabrik_extract_url'],
            'local_input_path': str(pbf),
            'source_sha256': source_hash, 'vector_sha256': sha256(stage / 'map.mbtiles'),
            'vector_layers': result['vector_layers'],
            'glyph_ranges_imported': result['glyph_ranges'],
            'graph_created': plan['route_graph_requested'],
            'graph_platform': 'OSRM MLD (server only)' if plan['route_graph_requested'] else None,
            'notice': 'Build output only. Not verified on Android, not yet published.',
        }
        (stage / 'build-receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        if dest.exists():
            raise FileExistsError('Сборка занята; нельзя перезаписывать')
        stage.rename(dest)
        receipt['output'] = str(dest)
        return receipt
    except BaseException:
        # Do not destroy partial data; operator can inspect logs and remove safely.
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list-regions', action='store_true')
    parser.add_argument('--region', choices=REGIONS)
    parser.add_argument('--pbf', type=Path)
    parser.add_argument('--version', default='2026.11')
    parser.add_argument('--output-root', type=Path, default=Path('VEXA_MAP/data/builds'))
    parser.add_argument('--tilemaker-config', type=Path)
    parser.add_argument('--tilemaker-process', type=Path)
    parser.add_argument('--osrm-profile', type=Path, help='Specify a real car.lua to build a SERVER OSRM graph')
    parser.add_argument('--glyphs-dir', type=Path, help='Licensed pre-generated MapLibre glyphs')
    parser.add_argument('--expected-sha256')
    parser.add_argument('--budget-gib', type=int, default=250)
    parser.add_argument('--reserve-gib', type=int, default=15)
    parser.add_argument('--tilemaker-bin', default='tilemaker')
    parser.add_argument('--osrm-prefix', default='')
    parser.add_argument('--execute', action='store_true', help='Explicitly start heavy local processing')
    args = parser.parse_args()
    if args.list_regions:
        print(json.dumps({k: source_url(k) for k in REGIONS}, indent=2))
        return
    if not all((args.region, args.pbf, args.tilemaker_config, args.tilemaker_process)):
        parser.error('--region, --pbf, --tilemaker-config, --tilemaker-process required')
    try:
        plan = build_plan(args.region, args.version, args.pbf, args.output_root,
                          args.tilemaker_config, args.tilemaker_process,
                          args.osrm_profile, args.budget_gib, args.reserve_gib,
                          args.tilemaker_bin, args.osrm_prefix)
        if args.execute:
            # Check paths also when working with external sources.
            for path in (args.tilemaker_config, args.tilemaker_process, args.osrm_profile):
                if path and not path.is_file():
                    raise ValueError(f'Не найден требуемый файл: {path}')
            print(json.dumps(execute_plan(plan, expected_sha256=args.expected_sha256,
                                          glyphs_dir=args.glyphs_dir), indent=2, ensure_ascii=False))
        else:
            print(json.dumps(plan, indent=2, ensure_ascii=False))
    except (ValueError, RuntimeError, FileNotFoundError, FileExistsError, OSError) as exc:
        parser.exit(2, f'VEXA MAP: {exc}\n')


if __name__ == '__main__':
    main()
