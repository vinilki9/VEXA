"""VEXA design system (introduced in 0.3.14): cross-platform contract checks.

These prove token/source wiring, NOT Android APK, Web build or visual device output.
"""
import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TOKENS = json.loads((ROOT / 'design/tokens.json').read_text(encoding='utf-8'))['colors']


def luminance(hex_value: str) -> float:
    raw = [int(hex_value[n:n+2], 16) / 255 for n in (1,3,5)]
    channels = [v / 12.92 if v <= 0.04045 else ((v+0.055)/1.055) ** 2.4 for v in raw]
    return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722


def contrast_ratio(a: str, b: str) -> float:
    values = sorted((luminance(a),luminance(b)))
    return (values[1] + .05) / (values[0] + .05)


def test_accessible_text_contrast():
    for fore,back in (
        ('primary','onPrimary'),
        ('navigation','graphite950'),
        ('textPrimary','graphite950'),
        ('textSecondary','graphite900'),
        ('lightPrimary','onPrimaryLight'),
        ('lightTextSecondary','canvas'),
    ):
        assert contrast_ratio(TOKENS[fore], TOKENS[back]) >= 4.5, (fore,back)


def test_android_color_schemes_generated_for_both_apps():
    versions = {}
    for app in ('client','driver'):
        path = ROOT / f'android/{app}/app/src/main/java/ru/vexa/{app}'
        source = (path / 'VexaDesign.kt').read_text()
        for key in ('primary','navigation','graphite950','graphite900'):
            assert 'Color(0xFF' + TOKENS[key][1:].upper() + ')' in source
        main = (path / 'MainActivity.kt').read_text()
        assert 'VexaDesign.darkScheme()' in main
        assert 'VexaDesign.lightScheme()' in main
        gradle = (ROOT / f'android/{app}/app/build.gradle.kts').read_text()
        name = re.search(r'(?m)^\s*versionName\s*=\s*"(\d+\.\d+\.\d+)"\s*$', gradle)
        code = re.search(r'(?m)^\s*versionCode\s*=\s*(\d+)\s*$', gradle)
        assert name and code, app
        version = tuple(map(int, name.group(1).split('.')))
        assert version >= (0, 3, 14), app
        assert int(code.group(1)) >= 14, app
        versions[app] = (version, int(code.group(1)))
    assert versions['client'] == versions['driver']


def test_dark_default_but_all_three_themes_available():
    client = (ROOT / 'android/client/app/src/main/java/ru/vexa/client/VexaClientPreferences.kt').read_text()
    driver = (ROOT / 'android/driver/app/src/main/java/ru/vexa/driver/DriverPreferences.kt').read_text()
    assert 'VexaThemeMode.DARK.name' in client
    assert 'val theme: String = "dark"' in driver
    assert 'SYSTEM, LIGHT, DARK' in client
    assert '"system", "light", "dark"' in driver


def test_web_dashboard_and_admin_same_palette():
    css_a = (ROOT / 'dispatcher/src/brand.css').read_text()
    css_b = (ROOT / 'platform-admin/src/vexa-brand.css').read_text()
    assert css_a == css_b
    for key in ('primary','navigation','graphite950','graphite900'):
        assert TOKENS[key] in css_a
    assert '@import "./vexa-brand.css"' in (ROOT / 'platform-admin/src/styles.css').read_text()
    assert 'color-scheme: dark' in (ROOT / 'dispatcher/src/style.css').read_text()


def test_android_route_color_exclusive_to_map_components():
    for app, file in (('client','VexaMapView.kt'),('driver','DriverMap.kt')):
        source = (ROOT / f'android/{app}/app/src/main/java/ru/vexa/{app}/{file}').read_text()
        assert 'VexaDesign.brightRoute.toArgb()' in source
    client = (ROOT / 'android/client/app/src/main/java/ru/vexa/client/MainActivity.kt').read_text()
    assert 'private val Teal = VexaDesign.mutedTeal' in client
    driver = (ROOT / 'android/driver/app/src/main/java/ru/vexa/driver/MainActivity.kt').read_text()
    assert 'private val VexaTeal = VexaDesign.mutedTeal' in driver


def test_passenger_order_card_respects_graphite():
    source = (ROOT / 'android/client/app/src/main/java/ru/vexa/client/PassengerOrderStatusPanel.kt').read_text()
    assert 'containerColor = MaterialTheme.colorScheme.surfaceVariant' in source
    assert 'Color(0xFFF7FAFA)' not in source
    assert 'MaterialTheme.colorScheme.onSurface' in source


def test_map_server_background_and_palette_metadata():
    map_root = ROOT / 'VEXA_MAP'
    service = (map_root / 'server/vexa_map_server.py').read_text()
    metadata = json.loads((map_root / 'design-palette.json').read_text())
    assert metadata['navigationRoute'] == TOKENS['navigation']
    assert metadata['marker'] == TOKENS['primary']
    assert metadata['background'] == TOKENS['graphite950']
    assert metadata['foreground'] == TOKENS['textPrimary']
    # Validate every style background, irrespective of Python quote style.
    backgrounds = []
    for node in ast.walk(ast.parse(service)):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == 'background-color':
                    assert isinstance(value, ast.Constant)
                    backgrounds.append(value.value)
    assert len(backgrounds) >= 3  # vector, raster, and no-data styles
    assert all(color == metadata['background'] for color in backgrounds)


def test_release_preserves_scoped_theme_and_wiring():
    assert (ROOT / 'tools/sync_design_tokens.py').exists()
    for app in ('client','driver'):
        source = (ROOT / f'android/{app}/app/src/main/java/ru/vexa/{app}/MainActivity.kt').read_text()
        assert 'MaterialTheme(' in source
    assert 'VEXA MAP' in (ROOT / 'android/client/app/src/main/java/ru/vexa/client/VexaMapView.kt').read_text()
