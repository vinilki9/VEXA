from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
IP = '45.143.139.162'
URL = 'https://' + IP


def test_android_debug_release_endpoints():
    for app in ('client', 'driver'):
        root = ROOT / 'android' / app
        props = (root / 'gradle.properties').read_text()
        gradle = (root / 'app/build.gradle.kts').read_text()
        assert f'vexaServerHost={IP}' in props
        assert 'vexaServerScheme=https' in props
        assert f'vexaReleaseApiBaseUrl={URL}' in props
        assert f'vexaReleaseMapBaseUrl={URL}/maps' in props
        assert ':8000' not in gradle and ':8090' not in gradle
        assert f'.orElse("{URL}")' in gradle
        assert f'.orElse("{URL}/maps")' in gradle


def test_production_gateway_and_internal_services():
    compose = yaml.safe_load((ROOT / 'infrastructure/compose.production.yml').read_text())
    services = compose['services']
    assert {k for k, v in services.items() if v.get('ports')} == {'gateway'}
    assert services['migrate']['environment']['ENVIRONMENT'] == 'production'
    assert IP in services['api']['environment']['PUBLIC_API_BASE_URL']
    assert IP in services['vexa_map']['environment']['VEXA_MAP_PUBLIC_BASE']
    caddy = (ROOT / 'infrastructure/Caddyfile.production').read_text()
    for path in ('/api/*', '/maps/*', '/dispatch/*', '/admin/*', '/health'):
        assert path in caddy
    assert 'profile shortlived' in caddy
    assert 'tls internal' not in caddy
    assert 'compose.production.yml' in (ROOT / 'tools/deploy_vps.sh').read_text()
