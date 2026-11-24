package ru.vexa.client

import android.content.Context
import ru.vexa.offline.OfflineMapMode
import ru.vexa.offline.OfflineMapConnectivity
import ru.vexa.offline.OfflineNavigation
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.Request
import org.json.JSONObject
import java.net.URLEncoder

/** Online VEXA MAP + offline regional index; never falls back to third-party maps. */
data class AddressResult(val name: String, val latitude: Double, val longitude: Double)

object AddressSearch {
    suspend fun search(context: Context, query: String): List<AddressResult> = withContext(Dispatchers.IO) {
        val mode = OfflineMapMode.load(context)
        val offline = mode == OfflineMapMode.OFFLINE ||
            (mode == OfflineMapMode.AUTO && !OfflineMapConnectivity.validatedInternet(context))
        suspend fun local(): List<AddressResult> {
            val nav = OfflineNavigation(context)
            if (nav.status().addressRegions.isEmpty())
                throw IllegalStateException("Нет офлайн-адресов: скачайте подготовленный пакет округа")
            return nav.search(query).map { AddressResult(it.name, it.latitude, it.longitude) }
        }
        if (offline) return@withContext local()
        try { onlineSearch(query) } catch (e: CancellationException) { throw e }
        catch (e: Exception) {
            if (mode == OfflineMapMode.ONLINE) throw e
            local()
        }
    }

    private suspend fun onlineSearch(query: String): List<AddressResult> = withContext(Dispatchers.IO) {
        val text = query.trim()
        if (text.isEmpty()) return@withContext emptyList()
        val encoded = URLEncoder.encode(text, "UTF-8")
        val req = Request.Builder()
            .url("${BuildConfig.VEXA_MAP_BASE_URL}/v1/search?q=$encoded")
            .get().build()
        ApiClient.client.newCall(req).execute().use { response ->
            val raw = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val detail = runCatching { JSONObject(raw).optString("error") }.getOrDefault("")
                throw IllegalStateException(detail.ifBlank { "VEXA MAP: поиск адресов недоступен (${response.code})" })
            }
            val list = JSONObject(raw).optJSONArray("results") ?: return@use emptyList()
            buildList {
                for (i in 0 until list.length()) {
                    val entry = list.optJSONObject(i) ?: continue
                    val lat = entry.optDouble("latitude", Double.NaN)
                    val lon = entry.optDouble("longitude", Double.NaN)
                    val name = entry.optString("name").trim()
                    if (name.isNotEmpty() && lat in -90.0..90.0 && lon in -180.0..180.0) {
                        add(AddressResult(name, lat, lon))
                    }
                }
            }
        }
    }
}
