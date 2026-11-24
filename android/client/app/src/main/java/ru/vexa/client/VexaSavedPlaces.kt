package ru.vexa.client

import android.content.Context
import org.json.JSONObject

/** Device-local favourites. Never saves authentication data or makes an order. */
internal object VexaSavedPlaces {
    private const val FILE = "vexa_client_places_v1"
    const val HOME = "home"
    const val WORK = "work"

    private fun accountKey(key: String): String? {
        val phone = ApiClient.getPassengerPhone()?.trim().orEmpty()
        if (phone.isBlank() || ApiClient.getAccessToken().isNullOrBlank()) return null
        val digest = java.security.MessageDigest.getInstance("SHA-256")
            .digest(phone.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
        return "$digest:$key"
    }

    fun load(context: Context, key: String): AddressResult? {
        if (key != HOME && key != WORK) return null
        val privateKey = accountKey(key) ?: return null
        val text = context.applicationContext.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            .getString(privateKey, null) ?: return null
        return runCatching {
            val value = JSONObject(text)
            val name = value.optString("name").trim()
            val latitude = value.optDouble("lat", Double.NaN)
            val longitude = value.optDouble("lon", Double.NaN)
            if (name.isBlank() || name.length > 500 || !latitude.isFinite() || !longitude.isFinite() ||
                latitude !in -90.0..90.0 || longitude !in -180.0..180.0
            ) null else AddressResult(name, latitude, longitude)
        }.getOrNull()
    }

    /** Clear only the signed-in passenger's own favourites, never another account's. */
    fun clearCurrentAccount(context: Context) {
        val homeKey = accountKey(HOME) ?: return
        val workKey = accountKey(WORK) ?: return
        context.applicationContext.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            .edit().remove(homeKey).remove(workKey).apply()
    }

    fun save(context: Context, key: String, point: AddressResult) {
        require(key == HOME || key == WORK) { "Неизвестный тип адреса" }
        require(point.name.isNotBlank() && point.name.length <= 500 &&
                point.latitude.isFinite() && point.longitude.isFinite() &&
                point.latitude in -90.0..90.0 && point.longitude in -180.0..180.0
        ) { "Выберите действительный адрес на карте" }
        val privateKey = accountKey(key)
            ?: throw IllegalStateException("Войдите в профиль, чтобы сохранить адрес")
        val value = JSONObject().put("name", point.name.trim())
            .put("lat", point.latitude).put("lon", point.longitude)
        context.applicationContext.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            .edit().putString(privateKey, value.toString()).apply()
    }
}
