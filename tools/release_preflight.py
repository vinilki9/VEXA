#!/usr/bin/env python3
"""Verify VEXA production configuration WITHOUT printing secrets.

This is a static gate, NOT a substitute for Docker Compose, migration and end-to-end tests.
"""
from __future__ import annotations

import argparse
import ipaddress
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_FILES = (
    'infrastructure/compose.production.yml',
    'infrastructure/Caddyfile.production',
    'android/client/app/build.gradle.kts',
    'android/driver/app/build.gradle.kts',
    'dispatcher/nginx-dispatcher.conf',
    'platform-admin/nginx-platform-admin.conf',
    'backend/alembic.ini',
    'VEXA_MAP/server/vexa_map_server.py',
)


def parse_env(raw: str) -> dict[str, str]:
    """Parse basic KEY=VALUE lines (not a shell interpreter)."""
    values: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            if value[:1] == value[-1:] and value.startswith(('"', "'")):
                value = value[1:-1]
            values[key] = value
    return values


def inspect_sources(root: Path) -> list[str]:
    errors = []
    for relative in PRODUCTION_FILES:
        if not (root / relative).is_file():
            errors.append(f'Отсутствует файл: {relative}')
    compose = root / 'infrastructure/compose.production.yml'
    if compose.is_file():
        content = compose.read_text(encoding='utf-8')
        # The public gate must be the only service exposing host ports.
        try:
            import yaml
        except ImportError:
            errors.append('Не установлен PyYAML для проверки портов (python -m pip install PyYAML)')
        else:
            document = yaml.safe_load(content)
            services = document.get('services', {})
            if not isinstance(services, dict):
                errors.append('В production Compose отсутствуют services')
            else:
                for name, item in services.items():
                    if name != 'gateway' and item.get('ports'):
                        errors.append(f'В production запрещена публикация порта у {name}')
                if not services.get('migrate'):
                    errors.append('Нет миграций Alembic перед запуском API')
                if not services.get('gateway', {}).get('ports'):
                    errors.append('Публичный HTTPS gateway не объявлен')
    return errors


def inspect_env(values: dict[str, str]) -> list[str]:
    errors: list[str] = []
    domain = values.get('VEXA_DOMAIN', '').strip()
    try:
        parsed_ip = ipaddress.ip_address(domain)
    except ValueError:
        parsed_ip = None
    is_public_ip = parsed_ip is not None and parsed_ip.version == 4 and parsed_ip.is_global
    valid_dns = parsed_ip is None and bool(re.fullmatch(r'(?=.{4,253}$)(?!-)[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+', domain)) and not re.fullmatch(r'[0-9.]+', domain) and not domain.endswith(('.example.com', '.invalid'))
    if not (is_public_ip or valid_dns):
        errors.append('VEXA_DOMAIN: укажите публичный IPv4 или действительное DNS-имя')
    if (not is_public_ip or values.get('VEXA_TLS_EMAIL')) and (not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', values.get('VEXA_TLS_EMAIL', '')) or 'example.' in values.get('VEXA_TLS_EMAIL', '')):
        errors.append('VEXA_TLS_EMAIL: укажите настоящий email для TLS')

    password = values.get('POSTGRES_PASSWORD', '')
    if len(password) < 24 or not re.fullmatch(r'[A-Za-z0-9_-]+', password) or 'REPLACE' in password:
        errors.append('POSTGRES_PASSWORD: нужен уникальный URL-safe пароль минимум из 24 символов')
    secret = values.get('SECRET_KEY', '')
    if len(secret) < 32 or any(t in secret for t in ('CHANGE_ME', 'REPLACE', 'example')):
        errors.append('SECRET_KEY: нужен другой случайный секрет минимум из 32 символов')
    if secret and password and secret == password:
        errors.append('SECRET_KEY должен отличаться от POSTGRES_PASSWORD')

    url = values.get('DATABASE_URL', '')
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != 'postgresql+psycopg' or parsed.hostname != 'db' or
            parsed.port != 5432 or parsed.username != values.get('POSTGRES_USER') or
            parsed.password != password or parsed.path != '/' + values.get('POSTGRES_DB', '')):
            errors.append('DATABASE_URL: настройки должны точно соответствовать DB и паролю')
    except (ValueError, AttributeError):
        errors.append('DATABASE_URL: неверный URL подключения к PostgreSQL')

    if values.get('ROUTING_PROVIDER', 'osrm') == 'osrm':
        r = values.get('OSRM_BASE_URL', '')
        m = values.get('VEXA_MAP_OSRM_URL', '')
        if bool(r) != bool(m) or (r and (r != m or r != 'http://osrm:5000')):
            errors.append('OSRM_BASE_URL и VEXA_MAP_OSRM_URL должны совпадать (http://osrm:5000), либо оба пусты')
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', type=Path, help='Existing .env.production file (do not commit)')
    parser.add_argument('--source-only', action='store_true', help='Check source files without credentials')
    args = parser.parse_args(argv)
    errors = inspect_sources(ROOT)
    if not args.source_only:
        if args.env is None or not args.env.is_file():
            errors.append('Нужен существующий приватный файл --env .env.production')
        else:
            errors.extend(inspect_env(parse_env(args.env.read_text(encoding='utf-8'))))
    if errors:
        print('VEXA release preflight: FAILED')
        for error in errors:
            print(' -', error)
        return 1
    print('VEXA release preflight: static checks passed (not proof of working deployment)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
