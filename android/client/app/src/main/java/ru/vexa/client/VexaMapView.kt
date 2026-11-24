package ru.vexa.client

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Surface
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.delay
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.Request
import org.json.JSONObject
import org.maplibre.android.MapLibre
import org.maplibre.android.annotations.MarkerOptions
import org.maplibre.android.annotations.PolylineOptions
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import ru.vexa.offline.OfflineMbtilesServer
import ru.vexa.offline.EffectiveMapSource
import ru.vexa.offline.MapSourcePolicy
import ru.vexa.offline.OfflineMapMode
import ru.vexa.offline.OfflineMapConnectivity
import ru.vexa.offline.NavigationCameraRules

@Composable
fun VexaMapView(pickup: AddressResult?, destination: AddressResult?, route: List<MapPoint>, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val offlineSource = remember(context) { OfflineMbtilesServer(context) }
    var mapMode by remember(context) { mutableStateOf(OfflineMapMode.load(context)) }
    var availableOffline by remember { mutableStateOf(false) }
    var hasInternet by remember { mutableStateOf(false) }
    var recheck by remember { mutableIntStateOf(0) }
    var styleVersion by remember { mutableIntStateOf(0) }
    val effectiveSource = MapSourcePolicy.choose(mapMode, availableOffline, hasInternet)
    val offlineSelected = effectiveSource == EffectiveMapSource.OFFLINE
    val view = remember(context) {
        MapLibre.getInstance(context)
        MapView(context).apply { onCreate(null) }
    }
    var map by remember { mutableStateOf<MapLibreMap?>(null) }
    var mapStatus by remember { mutableStateOf("Проверяем данные VEXA MAP...") }

    DisposableEffect(view, owner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> view.onStart()
                Lifecycle.Event.ON_RESUME -> { view.onResume(); recheck++ }
                Lifecycle.Event.ON_PAUSE -> view.onPause()
                Lifecycle.Event.ON_STOP -> view.onStop()
                else -> Unit
            }
        }
        owner.lifecycle.addObserver(observer)
        if (owner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) view.onStart()
        if (owner.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) view.onResume()
        onDispose { owner.lifecycle.removeObserver(observer); map = null; view.onDestroy(); offlineSource.close() }
    }

    LaunchedEffect(view) {
        view.getMapAsync { ready ->
            // Passenger map is always top-down, north-up: no 3D navigation or tilt gesture.
            ready.uiSettings.isTiltGesturesEnabled = false
            ready.uiSettings.isRotateGesturesEnabled = false
            ready.setMaxPitchPreference(0.0)
            ready.cameraPosition = CameraPosition.Builder().target(LatLng(55.751244, 37.618423))
                .zoom(11.0).tilt(NavigationCameraRules.PASSENGER_TILT)
                .bearing(NavigationCameraRules.PASSENGER_BEARING).build()
            map = ready
        }
    }
    // Network can disappear or return while navigation remains open.
    LaunchedEffect(context) {
        while (true) {
            val online = OfflineMapConnectivity.validatedInternet(context)
            if (online != hasInternet) hasInternet = online
            delay(10_000L)
        }
    }
    LaunchedEffect(recheck) {
        mapMode = OfflineMapMode.load(context)
        availableOffline = withContext(Dispatchers.IO) { offlineSource.refresh() > 0 }
        hasInternet = OfflineMapConnectivity.validatedInternet(context)
    }
    LaunchedEffect(map, mapMode, availableOffline, hasInternet, recheck) {
        val active = map ?: return@LaunchedEffect
        try {
            if (effectiveSource == EffectiveMapSource.UNAVAILABLE) {
                active.setStyle(Style.Builder().fromJson(
                    """{"version":8,"sources":{},"layers":[{"id":"background","type":"background","paint":{"background-color":"#151D21"}}]}"""
                )) { styleVersion++ }
                mapStatus = "Нет интернета и офлайн-карты. Подключитесь к сети или установите карту."
            } else if (offlineSelected) {
                if (!availableOffline) {
                    active.setStyle(Style.Builder().fromJson(
                        """{"version":8,"sources":{},"layers":[{"id":"background","type":"background","paint":{"background-color":"#151D21"}}]}"""
                    )) { styleVersion++ }
                    mapStatus = "Нет совместимых офлайн-карт. Скачайте растровый MBTiles или векторный PBF в настройках."
                } else {
                    val json = withContext(Dispatchers.IO) {
                        offlineSource.styleJson(offlineSource.start(), OfflineMapMode.preferredRegion(context), buildings3d = false)
                    }
                    active.setStyle(Style.Builder().fromJson(json)) {
                        styleVersion++
                        if (pickup == null && destination == null && route.isEmpty()) {
                            offlineSource.regionCenter(OfflineMapMode.preferredRegion(context))?.let { (lat, lon, zoom) ->
                                active.animateCamera(CameraUpdateFactory.newCameraPosition(CameraPosition.Builder()
                                    .target(LatLng(lat, lon)).zoom(zoom).tilt(0.0).bearing(0.0).build()))
                            }
                        }
                        mapStatus = offlineSource.mapDescription(OfflineMapMode.preferredRegion(context)) + " Маршрут сверху; офлайн-поиск — при наличии индекса."
                    }
                }
            } else {
                active.setStyle("${BuildConfig.VEXA_MAP_BASE_URL}/style.json") {
                    styleVersion++
                    mapStatus = ""
                }
            }
        } catch (error: Exception) {
            mapStatus = "Не удалось открыть карту: ${error.message}"
        }
    }
    LaunchedEffect(effectiveSource, map, styleVersion) {
        if (effectiveSource != EffectiveMapSource.ONLINE || map == null) return@LaunchedEffect
        mapStatus = try {
            withContext(Dispatchers.IO) {
                val req = Request.Builder().url("${BuildConfig.VEXA_MAP_BASE_URL}/health").build()
                ApiClient.client.newCall(req).execute().use { resp ->
                    if (!resp.isSuccessful) "Нет подключения к VEXA MAP" else {
                        val health = JSONObject(resp.body?.string().orEmpty())
                        if (!health.optBoolean("map_ready")) "На сервере ещё нет карт. Можно скачать офлайн-пакет." else ""
                    }
                }
            }
        } catch (_: Exception) { "Нет связи с VEXA MAP — проверьте адрес сервера" }
    }
    LaunchedEffect(map, styleVersion, pickup, destination, route) {
        val active = map ?: return@LaunchedEffect
        active.clear()
        pickup?.let { active.addMarker(MarkerOptions().position(LatLng(it.latitude,it.longitude)).title("Подача")) }
        destination?.let { active.addMarker(MarkerOptions().position(LatLng(it.latitude,it.longitude)).title("Назначение")) }
        if (route.size >= 2) {
            active.addPolyline(PolylineOptions().addAll(route.map { LatLng(it.latitude, it.longitude) })
                .color(VexaDesign.brightRoute.toArgb()).width(5f))
            val center = route[route.size / 2]
            active.animateCamera(CameraUpdateFactory.newCameraPosition(CameraPosition.Builder()
                .target(LatLng(center.latitude, center.longitude)).zoom(12.0).tilt(0.0).bearing(0.0).build()))
        } else (destination ?: pickup)?.let {
            active.animateCamera(CameraUpdateFactory.newCameraPosition(CameraPosition.Builder()
                .target(LatLng(it.latitude, it.longitude)).zoom(14.0).tilt(0.0).bearing(0.0).build()))
        }
    }
    Box(modifier) {
        AndroidView(factory = { view }, modifier = Modifier.fillMaxSize())
        Column(modifier = Modifier.align(Alignment.TopStart).padding(top = 60.dp, start = 8.dp, end = 8.dp)) {
            OutlinedButton(onClick = {
                mapMode = mapMode.next()
                OfflineMapMode.save(context, mapMode)
                recheck++
            }) { Text("Карта: ${mapMode.label}") }
            if (mapStatus.isNotBlank()) Surface {
                Text(mapStatus, modifier = Modifier.padding(8.dp))
            }
        }
    }
}
