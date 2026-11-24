package ru.vexa.client

import android.content.Context

/** Only real, device-local preferences are saved here. Auth tokens remain encrypted
 * in PassengerSessionStore, never in this ordinary preferences file. */
enum class VexaThemeMode { SYSTEM, LIGHT, DARK }

object VexaClientPreferences {
    private const val FILE_NAME = "vexa_client_preferences"
    private const val KEY_THEME = "theme_mode"
    private const val KEY_PAYMENT = "default_payment"

    val paymentMethods = listOf("Наличные", "Перевод водителю", "Банковская карта", "СБП")

    private fun preferences(context: Context) =
        context.applicationContext.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE)

    fun getTheme(context: Context): VexaThemeMode =
        runCatching {
            VexaThemeMode.valueOf(
                preferences(context).getString(KEY_THEME, VexaThemeMode.DARK.name).orEmpty()
            )
        }.getOrDefault(VexaThemeMode.DARK)

    fun setTheme(context: Context, theme: VexaThemeMode) {
        preferences(context).edit().putString(KEY_THEME, theme.name).apply()
    }

    fun getDefaultPayment(context: Context): String =
        preferences(context).getString(KEY_PAYMENT, null)
            ?.takeIf { it in paymentMethods } ?: "Наличные"

    fun setDefaultPayment(context: Context, method: String) {
        require(method in paymentMethods) { "Неизвестный способ оплаты" }
        preferences(context).edit().putString(KEY_PAYMENT, method).apply()
    }
}
