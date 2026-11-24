"""Source-level regression tests only; do not substitute for an Android APK build."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "android/client/app/src/main/java/ru/vexa/client"
MAIN = (SRC / "MainActivity.kt").read_text(encoding="utf-8")
SETTINGS = (SRC / "VexaClientSettingsScreen.kt").read_text(encoding="utf-8")
PREFS = (SRC / "VexaClientPreferences.kt").read_text(encoding="utf-8")
GRADLE = (ROOT / "android/client/app/build.gradle.kts").read_text(encoding="utf-8")


def test_three_dots_in_upper_right_open_settings():
    assert "Icons.Default.MoreVert" in MAIN
    assert "Alignment.TopEnd" in MAIN
    assert 'contentDescription = "Открыть настройки приложения"' in MAIN
    assert "onClick = onOpenSettings" in MAIN
    assert "settingsOpen = true" in MAIN


def test_settings_are_overlay_not_destructive_navigation():
    assert "ClientScreen(" in MAIN
    assert "if (settingsOpen)" in MAIN
    assert "Dialog(" in MAIN
    assert "VexaClientSettingsScreen(" in MAIN
    assert "BackHandler { settingsRevision++; settingsOpen = false }" in MAIN
    assert 'contentDescription = "Назад к карте"' in SETTINGS


def test_real_login_logout_uses_existing_secure_session():
    assert "PassengerAuthDialog(" in SETTINGS
    assert "ApiClient.getPassengerPhone()" in SETTINGS
    assert "ApiClient.clearAccessToken()" in SETTINGS
    assert "confirmLogout" in SETTINGS
    assert "PassengerSessionStore" in (SRC / "ApiClient.kt").read_text(encoding="utf-8")


def test_theme_and_payment_are_persisted_and_used_by_home():
    assert "SharedPreferences" in PREFS or "getSharedPreferences" in PREFS
    assert "KEY_THEME" in PREFS and "KEY_PAYMENT" in PREFS
    assert "VexaThemeMode.SYSTEM" in SETTINGS
    assert "VexaThemeMode.LIGHT" in SETTINGS
    assert "VexaThemeMode.DARK" in SETTINGS
    theme = (SRC / "VexaDesign.kt").read_text(encoding="utf-8")
    assert "darkColorScheme" in theme and "lightColorScheme" in theme
    assert "VexaDesign.darkScheme()" in MAIN and "VexaDesign.lightScheme()" in MAIN
    assert "mutableStateOf(defaultPayment)" in MAIN
    assert "LaunchedEffect(defaultPayment)" in MAIN
    assert "VexaClientPreferences.setDefaultPayment" in MAIN


def test_permission_management_is_really_android_settings():
    assert "Settings.ACTION_APPLICATION_DETAILS_SETTINGS" in SETTINGS
    assert "ContextCompat.checkSelfPermission" in SETTINGS
    assert "Lifecycle.Event.ON_RESUME" in SETTINGS
    assert "context.startActivity(intent)" in SETTINGS


def test_settings_do_not_claim_unimplemented_push_services():
    for false_claim in ("Включить push-уведомления", "Удалить аккаунт навсегда"):
        assert false_claim not in SETTINGS
    assert "BuildConfig.VERSION_NAME" in SETTINGS
    assert "VEXA MAP / MapLibre" in SETTINGS


def test_version_and_manifest():
    assert int(re.search(r"versionCode\s*=\s*(\d+)", GRADLE).group(1)) >= 6
    assert re.search(r'versionName\s*=\s*"0\.3\.\d+"', GRADLE)
    ET.parse(ROOT / "android/client/app/src/main/AndroidManifest.xml")


def test_settings_marked_as_actual_code_not_spec():
    assert re.search(r"fun VexaClientSettingsScreen\s*\(", SETTINGS)
    assert "onThemeModeChange(mode)" in SETTINGS
    assert "onDefaultPaymentChange(method)" in SETTINGS
