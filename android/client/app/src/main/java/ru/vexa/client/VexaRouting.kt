package ru.vexa.client

import android.content.Context
import ru.vexa.offline.OfflineMapMode
import ru.vexa.offline.OfflineMapConnectivity
import ru.vexa.offline.OfflineNavigation
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.Request
import org.json.JSONObject

/** Route preview from VEXA MAP online OSRM or a bounded local district road graph. */
data class MapPoint(val latitude: Double, val longitude: Double)
data class VexaRoute(val line: List<MapPoint>, val meters: Double, val seconds: Double, val offline: Boolean = false)

object VexaRouting {
    suspend fun route(context: Context, start: AddressResult, end: AddressResult): VexaRoute = withContext(Dispatchers.IO) {
        val mode = OfflineMapMode.load(context)
        val offline = mode == OfflineMapMode.OFFLINE ||
            (mode == OfflineMapMode.AUTO && !OfflineMapConnectivity.validatedInternet(context))
        suspend fun local(): VexaRoute {
            val route = OfflineNavigation(context).route(start.latitude, start.longitude, end.latitude, end.longitude)
            return VexaRoute(route.points.map { MapPoint(it.latitude, it.longitude) },
                route.meters, route.seconds, offline = true)
        }
        if (offline) return@withContext local()
        try { onlineRoute(start, end) } catch (e: CancellationException) { throw e }
        catch (e: Exception) {
            if (mode == OfflineMapMode.ONLINE) throw e
            local()
        }
    }

    private suspend fun onlineRoute(start: AddressResult, end: AddressResult): VexaRoute = withContext(Dispatchers.IO) {
        val url = "${BuildConfig.VEXA_MAP_BASE_URL}/v1/route".toHttpUrl().newBuilder()
            .addQueryParameter("start_lat", start.latitude.toString())
            .addQueryParameter("start_lon", start.longitude.toString())
            .addQueryParameter("end_lat", end.latitude.toString())
            .addQueryParameter("end_lon", end.longitude.toString())
            .build()
        val request = Request.Builder().url(url).get().build()
        ApiClient.client.newCall(request).execute().use { response ->
            val raw = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val msg = runCatching { JSONObject(raw).optString("error") }.getOrDefault("")
                throw IllegalStateException(msg.ifBlank { "Маршрутизация VEXA MAP недоступна (${response.code})" })
            }
            val result = JSONObject(raw)
            val coords = result.getJSONObject("geometry").getJSONArray("coordinates")
            val line = buildList {
                for (i in 0 until coords.length()) {
                    val coordinate = coords.getJSONArray(i)
                    add(MapPoint(coordinate.getDouble(1), coordinate.getDouble(0)))
                }
            }
            require(line.size >= 2) { "VEXA MAP вернул пустой маршрут" }
            VexaRoute(line, result.getDouble("distance_meters"), result.getDouble("duration_seconds"))
        }
    }
}
