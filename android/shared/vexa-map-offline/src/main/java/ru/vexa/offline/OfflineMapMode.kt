package ru.vexa.offline

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import androidx.compose.runtime.mutableIntStateOf

/** The preference is stored per application; never implies offline routing. */
enum class OfflineMapMode(val label: String) {
    AUTO("Авто"), ONLINE("Онлайн"), OFFLINE("Офлайн");
    fun next(): OfflineMapMode = entries[(ordinal + 1) % entries.size]

    companion object {
        private const val PREFS = "vexa_map_display"
        /** In-process signal: recalculate route after switching map modes. */
        val changeCounter = mutableIntStateOf(0)
        fun load(context: Context): OfflineMapMode {
            val saved = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString("mode", AUTO.name)
            return entries.firstOrNull { it.name == saved } ?: AUTO
        }
        fun save(context: Context, mode: OfflineMapMode) {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putString("mode", mode.name).apply()
            changeCounter.intValue++
        }
        fun preferredRegion(context: Context): String? =
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString("region", null)?.takeIf(OfflineMapRules::validRegion)
        fun selectRegion(context: Context, regionId: String) {
            require(OfflineMapRules.validRegion(regionId))
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putString("region", regionId).putString("mode", OFFLINE.name).apply()
            changeCounter.intValue++
        }
    }
}

object OfflineMapConnectivity {
    fun validatedInternet(context: Context): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return false
        val caps = cm.getNetworkCapabilities(cm.activeNetwork) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }
}
