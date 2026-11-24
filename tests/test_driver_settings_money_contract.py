"""Static source-contract tests for the Android driver settings and money shortcuts.

These tests inspect wiring in source, not Android runtime/Gradle compilation.
"""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "android/driver/app/src/main/java/ru/vexa/driver"


class DriverSettingsMoneyContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (SRC / "MainActivity.kt").read_text(encoding="utf-8")
        cls.finance = (SRC / "DriverFinanceActivity.kt").read_text(encoding="utf-8")
        cls.panel = (SRC / "DriverFinancePanel.kt").read_text(encoding="utf-8")
        cls.api = (SRC / "DriverApiClient.kt").read_text(encoding="utf-8")
        cls.manifest = (ROOT / "android/driver/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        cls.settings = (SRC / "DriverSettingsScreen.kt").read_text(encoding="utf-8")
        cls.preferences = (SRC / "DriverPreferences.kt").read_text(encoding="utf-8")
        cls.service = (SRC / "DriverLocationService.kt").read_text(encoding="utf-8")

    def test_money_button_on_home_opens_finances(self):
        self.assertIn('text = "ДЕНЬГИ"', self.main)
        self.assertIn('Intent(context, DriverFinanceActivity::class.java)', self.main)
        self.assertIn('text = "Баланс, заработок, комиссия и история операций"', self.main)

    def test_finance_activity_is_manifest_registered(self):
        self.assertIn('android:name=".DriverFinanceActivity"', self.manifest)
        self.assertIn('text = "Деньги"', self.finance)
        self.assertIn('DriverFinancePanel(', self.finance)

    def test_finances_get_real_api_data(self):
        self.assertIn('getWalletTransactions(', self.panel)
        self.assertIn('getWallet()', self.api)
        self.assertIn('DriverApiClient.getFinanceSummary()', self.panel)
        self.assertIn('"/api/v1/driver/wallet"', self.api)
        self.assertIn('"/api/v1/driver/wallet/transactions"', self.api)

    def test_money_screen_follows_saved_theme(self):
        self.assertIn('DriverPreferences.load(context).theme', self.finance)
        self.assertIn('dark = dark,', self.finance)
        self.assertIn('isSystemInDarkTheme()', self.finance)

    def test_settings_entry_and_page_connected(self):
        self.assertIn('contentDescription = "Настройки VEXA Driver"', self.main)
        self.assertIn('DriverSettingsScreen(', self.main)
        self.assertIn('onValueChange = ::updatePreferences', self.main)
        self.assertIn('DriverPreferences.save(context, next)', self.main)
        self.assertIn('"Настройки водителя"', self.settings)

    def test_offer_notification_is_deduplicated_by_id(self):
        alerts = (SRC / "DriverOfferAlerts.kt").read_text(encoding="utf-8")
        self.assertIn('DriverOfferAlertPolicy.newOfferId(', alerts)
        self.assertIn('DriverOfferAlerts.onPoll(this@DriverLocationService, response)', self.service)


if __name__ == '__main__':
    unittest.main()
