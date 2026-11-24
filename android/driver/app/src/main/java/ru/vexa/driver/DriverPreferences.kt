package ru.vexa.driver

import android.content.Context

/** Локальные настройки интерфейса и оповещений, без паролей или персональных данных. */
internal object DriverPreferences {
    private const val PREFS = "vexa_driver_ui_preferences_v1"
    private val themes = setOf("system", "light", "dark")
    private val soundProfiles = setOf("classic", "modern", "soft", "dynamic", "calm", "premium")

    data class State(
        val theme: String = "dark",
        val soundProfile: String = "classic",
        val alertsEnabled: Boolean = true,
        val vibrationEnabled: Boolean = true,
        val volume: Int = 70,
        val followGps: Boolean = true
    )

    fun load(context: Context): State {
        val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val theme = prefs.getString("theme", "dark").orEmpty().takeIf { it in themes } ?: "dark"
        val sound = prefs.getString("sound_profile", "classic").orEmpty()
            .takeIf { it in soundProfiles } ?: "classic"
        return State(
            theme = theme,
            soundProfile = sound,
            alertsEnabled = prefs.getBoolean("alerts_enabled", true),
            vibrationEnabled = prefs.getBoolean("vibration_enabled", true),
            volume = prefs.getInt("alert_volume", 70).coerceIn(0, 100),
            followGps = prefs.getBoolean("follow_gps", true)
        )
    }

    fun save(context: Context, value: State) {
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString("theme", value.theme.takeIf { it in themes } ?: "dark")
            .putString("sound_profile", value.soundProfile.takeIf { it in soundProfiles } ?: "classic")
            .putBoolean("alerts_enabled", value.alertsEnabled)
            .putBoolean("vibration_enabled", value.vibrationEnabled)
            .putInt("alert_volume", value.volume.coerceIn(0, 100))
            .putBoolean("follow_gps", value.followGps)
            .apply()
    }
}
