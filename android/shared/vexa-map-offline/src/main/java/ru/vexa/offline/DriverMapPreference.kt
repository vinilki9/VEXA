package ru.vexa.offline

import android.content.Context

/** Per-driver preference; the passenger app never imports or exposes this mode. */
object DriverMapPreference {
    private const val KEY = "driver_perspective"
    fun load(context: Context): DriverMapPerspective {
        val stored = context.getSharedPreferences("vexa_map_display", Context.MODE_PRIVATE)
            .getString(KEY, DriverMapPerspective.TWO_D.name)
        return DriverMapPerspective.entries.firstOrNull { it.name == stored } ?: DriverMapPerspective.TWO_D
    }
    fun save(context: Context, perspective: DriverMapPerspective) {
        context.getSharedPreferences("vexa_map_display", Context.MODE_PRIVATE)
            .edit().putString(KEY, perspective.name).apply()
    }
}
