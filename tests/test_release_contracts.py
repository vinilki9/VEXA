from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_android_release_uses_https_parameters_and_debug_keeps_local_override():
    for app in ('client', 'driver'):
        path = ROOT / f'android/{app}/app/build.gradle.kts'
        source = path.read_text()
        for setting in ('vexaReleaseApiBaseUrl', 'vexaReleaseMapBaseUrl', 'vexaServerHost'):
            assert setting in source, f'{app}: missing {setting}'
        assert 'manifestPlaceholders["vexaCleartext"] = "false"' in source
        assert 'https://' in source
        import re
        version = re.search(r'versionCode\s*=\s*(\d+)', source)
        assert version is not None and int(version.group(1)) >= 5
        manifest = (ROOT / f'android/{app}/app/src/main/AndroidManifest.xml').read_text()
        assert 'android:allowBackup="false"' in manifest


def test_ui_brand_color_consistency():
    """Shared palette is generated from one token file, not hand-copied hex codes."""
    import json
    token = json.loads((ROOT / 'design/tokens.json').read_text())['colors']
    for path in ('dispatcher/src/brand.css', 'platform-admin/src/vexa-brand.css'):
        css = (ROOT / path).read_text().lower()
        assert token['primary'].lower() in css, path
        assert token['navigation'].lower() in css, path
    for app in ('client', 'driver'):
        root = ROOT / f'android/{app}/app/src/main/java/ru/vexa/{app}'
        theme = (root / 'VexaDesign.kt').read_text()
        assert 'Color(0xFF' + token['primary'][1:].upper() + ')' in theme
        assert 'Color(0xFF' + token['navigation'][1:].upper() + ')' in theme
        assert 'VexaDesign.darkScheme()' in (root / 'MainActivity.kt').read_text()


def test_dispatcher_health_indicator_is_verified():
    ui = (ROOT / 'dispatcher/src/main.tsx').read_text()
    nginx = (ROOT / 'dispatcher/nginx-dispatcher.conf').read_text()
    assert 'body?.service === \'vexa-api\'' in ui
    assert 'serverOnline === null' in ui
    assert 'location = /health' in nginx


def test_admin_network_error_has_retry_without_signout():
    ui = (ROOT / 'platform-admin/src/App.tsx').read_text()
    assert 'setSessionFailed(true)' in ui
    assert 'Повторить проверку' in ui
    assert 'response.status === 401 || response.status === 403' in ui


def test_backend_production_docs_disabled():
    code = (ROOT / 'backend/app/main.py').read_text()
    assert 'docs_url=None if _production_mode' in code
    assert 'openapi_url=None if _production_mode' in code


def test_prod_gateway_routes_protected_and_public_paths():
    caddy = (ROOT / 'infrastructure/Caddyfile.production').read_text()
    assert 'handle_path /dispatch/*' in caddy
    assert 'handle_path /admin/*' in caddy
    assert 'handle_path /maps/*' in caddy
    assert 'X-Forwarded-Prefix /maps' in caddy
    assert 'handle /api/*' in caddy
