from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = spec_from_file_location('preflight', root / 'tools/release_preflight.py')
assert spec and spec.loader
preflight = module_from_spec(spec)
spec.loader.exec_module(preflight)


def valid_env():
    return {
        'VEXA_DOMAIN': 'taxi.company.ru',
        'VEXA_TLS_EMAIL': 'admin@company.ru',
        'POSTGRES_DB': 'vexa',
        'POSTGRES_USER': 'vexa_app',
        'POSTGRES_PASSWORD': 'uniquePass_0123456789_L0ngEnough',
        'DATABASE_URL': 'postgresql+psycopg://vexa_app:uniquePass_0123456789_L0ngEnough@db:5432/vexa',
        'SECRET_KEY': 'different_secret_key_0123456789_abcdefghijklmnopqrstuvwxyz',
        'ROUTING_PROVIDER': 'osrm',
        'OSRM_BASE_URL': '',
        'VEXA_MAP_OSRM_URL': '',
    }


def test_source_structure_has_no_public_internal_ports():
    assert not preflight.inspect_sources(root)


def test_valid_production_env():
    assert not preflight.inspect_env(valid_env())


def test_examples_and_short_secrets_rejected():
    bad = valid_env()
    bad.update(VEXA_DOMAIN='taxi.example.com', POSTGRES_PASSWORD='short', SECRET_KEY='short', VEXA_TLS_EMAIL='admin@example.com')
    assert len(preflight.inspect_env(bad)) >= 4


def test_wrong_db_password_rejected():
    bad = valid_env()
    bad['POSTGRES_PASSWORD'] = 'different_password_0123456789_______'
    assert any('DATABASE_URL' in m for m in preflight.inspect_env(bad))


def test_osrm_configuration_consistency():
    good = valid_env()
    good['OSRM_BASE_URL'] = 'http://osrm:5000'
    good['VEXA_MAP_OSRM_URL'] = 'http://osrm:5000'
    assert not preflight.inspect_env(good)
    good['VEXA_MAP_OSRM_URL'] = ''
    assert any('OSRM' in m for m in preflight.inspect_env(good))


def test_parse_env_quoted_values():
    parsed = preflight.parse_env('''# comment\nA=value\nexport B="quoted value"\nC='other'\n''')
    assert parsed == {'A': 'value', 'B': 'quoted value', 'C': 'other'}
