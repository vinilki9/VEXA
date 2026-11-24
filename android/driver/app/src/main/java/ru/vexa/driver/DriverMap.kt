package ru.vexa.driver

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Looper
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.delay
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import org.maplibre.android.MapLibre
import org.maplibre.android.annotations.MarkerOptions
import org.maplibre.android.annotations.PolylineOptions
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.Style
import ru.vexa.offline.OfflineMbtilesServer
import ru.vexa.offline.EffectiveMapSource
import ru.vexa.offline.MapSourcePolicy
import ru.vexa.offline.OfflineMapMode
import ru.vexa.offline.OfflineMapConnectivity
import ru.vexa.offline.OfflineNavigation
import ru.vexa.offline.DriverMapPerspective
import ru.vexa.offline.DriverMapPreference
import ru.vexa.offline.NavigationCameraRules
import ru.vexa.offline.GpsSmoother
import ru.vexa.offline.NavFix
import ru.vexa.offline.NavPoint
import ru.vexa.offline.RouteMatcher
import ru.vexa.offline.RerouteGate
import ru.vexa.offline.CameraMotion
import ru.vexa.offline.RoadAwareMatcher
import ru.vexa.offline.RoadMatch
import java.util.concurrent.TimeUnit

private data class DriverPoint(val latitude: Double, val longitude: Double)
private val routeHttp = OkHttpClient.Builder().connectTimeout(8, TimeUnit.SECONDS)
    .readTimeout(15, TimeUnit.SECONDS).build()

private fun JSONObject?.point(name: String): DriverPoint? {
    val point = this?.optJSONObject(name) ?: return null
    val lat = point.optDouble("latitude", Double.NaN)
    val lon = point.optDouble("longitude", Double.NaN)
    return if (lat in -90.0..90.0 && lon in -180.0..180.0) DriverPoint(lat, lon) else null
}

private suspend fun fetchDriverRoute(start: DriverPoint, end: DriverPoint): List<DriverPoint> =
    withContext(Dispatchers.IO) {
        val base = "${BuildConfig.VEXA_MAP_BASE_URL}/v1/route".toHttpUrl()
        val url = base.newBuilder()
            .addQueryParameter("start_lat", start.latitude.toString())
            .addQueryParameter("start_lon", start.longitude.toString())
            .addQueryParameter("end_lat", end.latitude.toString())
            .addQueryParameter("end_lon", end.longitude.toString())
            .build()
        routeHttp.newCall(Request.Builder().url(url).get().build()).execute().use { response ->
            val raw = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val error = runCatching { JSONObject(raw).optString("error") }.getOrDefault("")
                throw IllegalStateException(error.ifBlank { "Маршрутизация не настроена (${response.code})" })
            }
            val coordinates = JSONObject(raw).getJSONObject("geometry").getJSONArray("coordinates")
            buildList {
                for (i in 0 until coordinates.length()) {
                    val xy = coordinates.getJSONArray(i)
                    add(DriverPoint(xy.getDouble(1), xy.getDouble(0)))
                }
            }
        }
    }

/** Driver ride preview on VEXA MAP; GPS updates and route preview are separate from background dispatch GPS. */
@Composable
fun DriverMap(modifier: Modifier = Modifier, activeOrder: JSONObject? = null, autoCenter: Boolean = true) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val offlineSource = remember(context) { OfflineMbtilesServer(context) }
    var mapMode by remember(context) { mutableStateOf(OfflineMapMode.load(context)) }
    var perspective by remember(context) { mutableStateOf(DriverMapPreference.load(context)) }
    var availableOffline by remember { mutableStateOf(false) }
    var hasInternet by remember { mutableStateOf(false) }
    var recheck by remember { mutableIntStateOf(0) }
    var styleVersion by remember { mutableIntStateOf(0) }
    val effectiveSource = MapSourcePolicy.choose(mapMode, availableOffline, hasInternet)
    val offlineSelected = effectiveSource == EffectiveMapSource.OFFLINE
    val mapView = remember(context) {
        MapLibre.getInstance(context)
        MapView(context).apply { onCreate(null) }
    }
    val locationManager = remember(context) { context.getSystemService(Context.LOCATION_SERVICE) as LocationManager }
    var map by remember { mutableStateOf<MapLibreMap?>(null) }
    var location by remember { mutableStateOf<Location?>(null) }
    val gpsSmoother = remember { GpsSmoother() }
    val rerouteGate = remember { RerouteGate() }
    var rerouteMessage by remember { mutableStateOf("") }
    var rerouteRequest by remember { mutableIntStateOf(0) }
    var rerouteStart by remember { mutableStateOf<DriverPoint?>(null) }
    var statusMessage by remember { mutableStateOf("VEXA MAP: определяем GPS...") }
    var followDriver by remember { mutableStateOf(true) }
    var mapDataMessage by remember { mutableStateOf("Проверяем наличие карт...") }
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
    LaunchedEffect(map, mapMode, perspective, availableOffline, hasInternet, recheck) {
        val active = map ?: return@LaunchedEffect
        try {
            if (effectiveSource == EffectiveMapSource.UNAVAILABLE) {
                active.setStyle(Style.Builder().fromJson(
                    """{"version":8,"sources":{},"layers":[{"id":"background","type":"background","paint":{"background-color":"#151D21"}}]}"""
                )) { styleVersion++ }
                mapDataMessage = "Нет интернета и офлайн-карты. Подключитесь к сети или установите регион."
            } else if (offlineSelected) {
                if (!availableOffline) {
                    active.setStyle(Style.Builder().fromJson(
                        """{"version":8,"sources":{},"layers":[{"id":"background","type":"background","paint":{"background-color":"#151D21"}}]}"""
                    )) { styleVersion++ }
                    mapDataMessage = "Скачайте совместимый MBTiles/PBF округ в настройках карт."
                } else {
                    val json = withContext(Dispatchers.IO) {
                        offlineSource.styleJson(offlineSource.start(), OfflineMapMode.preferredRegion(context), buildings3d = perspective == DriverMapPerspective.THREE_D)
                    }
                    active.setStyle(Style.Builder().fromJson(json)) {
                        styleVersion++
                        if (location == null && activeOrder == null) {
                            offlineSource.regionCenter(OfflineMapMode.preferredRegion(context))?.let { (lat, lon, zoom) ->
                                active.animateCamera(CameraUpdateFactory.newCameraPosition(CameraPosition.Builder()
                                    .target(LatLng(lat, lon)).zoom(zoom)
                                    .tilt(NavigationCameraRules.driverTilt(perspective)).build()))
                            }
                        }
                        mapDataMessage = offlineSource.mapDescription(OfflineMapMode.preferredRegion(context)) + " Маршрут — при наличии дорожного графа."
                    }
                }
            } else {
                val styleUrl = "${BuildConfig.VEXA_MAP_BASE_URL}/style.json" +
                    if (perspective == DriverMapPerspective.THREE_D) "?view=3d" else ""
                active.setStyle(styleUrl) {
                    styleVersion++
                    mapDataMessage = ""
                }
            }
        } catch (error: Exception) {
            mapDataMessage = "Ошибка карты: ${error.message}"
        }
    }
    LaunchedEffect(effectiveSource, map, styleVersion) {
        if (effectiveSource != EffectiveMapSource.ONLINE || map == null) return@LaunchedEffect
        mapDataMessage = try {
            withContext(Dispatchers.IO) {
                routeHttp.newCall(Request.Builder().url("${BuildConfig.VEXA_MAP_BASE_URL}/health").build())
                    .execute().use { response ->
                        if (!response.isSuccessful) "Сервис карт не отвечает" else {
                            val health = JSONObject(response.body?.string().orEmpty())
                            if (health.optBoolean("map_ready")) "" else "На сервере нет пакета MBTiles"
                        }
                    }
            }
        } catch (_: Exception) { "VEXA MAP недоступна — проверьте адрес сервера" }
    }
    var roadMatch by remember { mutableStateOf<RoadMatch?>(null) }
    var previousRoadEdgeId by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(location, offlineSelected, availableOffline) {
        val fix = location
        if (!offlineSelected || !availableOffline || fix == null ||
            !fix.hasAccuracy() || fix.accuracy > 25f) {
            roadMatch = null
            return@LaunchedEffect
        }
        val candidates = OfflineNavigation(context).nearbyRoadEdges(fix.latitude, fix.longitude)
        val result = RoadAwareMatcher.match(NavPoint(fix.latitude, fix.longitude),
            fix.accuracy.toDouble(), candidates,
            if (fix.hasBearing() && fix.hasSpeed() && fix.speed > 2f) fix.bearing.toDouble() else null,
            previousRoadEdgeId)
        roadMatch = result
        if (result?.confident == true && !result.ambiguous) previousRoadEdgeId = result.edgeId
    }
    var routeMessage by remember { mutableStateOf("") }
    var routeLine by remember { mutableStateOf<List<DriverPoint>>(emptyList()) }
    LaunchedEffect(routeLine) { rerouteGate.reset(); rerouteMessage = "" }
    LaunchedEffect(location, routeLine, roadMatch, offlineSelected) {
        val fix = location ?: return@LaunchedEffect
        val deviation = RouteMatcher.project(
            NavPoint(fix.latitude, fix.longitude),
            routeLine.map { NavPoint(it.latitude, it.longitude) }
        )?.deviationMeters ?: return@LaunchedEffect
        // Offline: a graph-backed confident match is mandatory before automatic reroute.
        // If graph data are absent or multiple roads are indistinguishable, stay conservative.
        val trustworthy = fix.hasAccuracy() && fix.accuracy <= 25f &&
            (!offlineSelected || (roadMatch?.confident == true && roadMatch?.ambiguous == false))
        if (rerouteGate.observe(deviation, fix.elapsedRealtimeNanos / 1_000_000L, trustworthy)) {
            rerouteMessage = "Перестраиваем маршрут…"
            rerouteStart = DriverPoint(fix.latitude, fix.longitude)
            rerouteRequest++
        } else if (deviation < 20.0) rerouteMessage = ""
    }
    var permission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
                ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        )
    }
    val requestPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { grants ->
        permission = grants.values.any { it }
    }

    DisposableEffect(lifecycleOwner, mapView) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> mapView.onStart()
                Lifecycle.Event.ON_RESUME -> { mapView.onResume(); recheck++ }
                Lifecycle.Event.ON_PAUSE -> mapView.onPause()
                Lifecycle.Event.ON_STOP -> mapView.onStop()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        if (lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) mapView.onStart()
        if (lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) mapView.onResume()
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer); map = null; mapView.onDestroy(); offlineSource.close() }
    }

    LaunchedEffect(mapView) {
        mapView.getMapAsync { ready ->
            ready.cameraPosition = CameraPosition.Builder().target(LatLng(54.98, 37.23))
                .zoom(13.0).tilt(NavigationCameraRules.driverTilt(perspective)).build()
            map = ready
        }
    }

    // Mode belongs only to Driver. In 2D there is no tilt or rotation; 3D follows GPS course.
    LaunchedEffect(map, perspective) {
        val active = map ?: return@LaunchedEffect
        val threeD = perspective == DriverMapPerspective.THREE_D
        active.uiSettings.isTiltGesturesEnabled = threeD
        active.uiSettings.isRotateGesturesEnabled = threeD
        active.setMaxPitchPreference(if (threeD) 60.0 else 0.0)
        val previous = active.cameraPosition
        val heading = location?.takeIf { it.hasBearing() }?.bearing?.toDouble()
        active.animateCamera(CameraUpdateFactory.newCameraPosition(CameraPosition.Builder()
            .target(previous.target).zoom(if (threeD) maxOf(previous.zoom, 15.5) else previous.zoom)
            .tilt(NavigationCameraRules.driverTilt(perspective))
            .bearing(NavigationCameraRules.driverBearing(perspective, heading)).build()))
    }

    DisposableEffect(permission) {
        if (!permission) {
            statusMessage = "Разрешите доступ к GPS"
            onDispose { }
        } else {
            val provider = when {
                locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER) -> LocationManager.GPS_PROVIDER
                locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER) -> LocationManager.NETWORK_PROVIDER
                else -> null
            }
            if (provider == null) {
                statusMessage = "Включите определение местоположения"
                onDispose { }
            } else {
                val listener = object : LocationListener {
                    override fun onLocationChanged(newLocation: Location) {
                        val result = gpsSmoother.update(NavFix(
                            NavPoint(newLocation.latitude, newLocation.longitude),
                            newLocation.accuracy.toDouble(),
                            newLocation.elapsedRealtimeNanos / 1_000_000L
                        ))
                        if (result.accepted && result.point != null) {
                            location = Location(newLocation).apply {
                                latitude = result.point.latitude
                                longitude = result.point.longitude
                            }
                            statusMessage = "GPS: %.5f, %.5f".format(result.point.latitude, result.point.longitude)
                        } else statusMessage = "GPS: пропущено неточное измерение"
                    }
                    override fun onStatusChanged(p: String?, s: Int, extras: Bundle?) = Unit
                    override fun onProviderEnabled(p: String) = Unit
                    override fun onProviderDisabled(p: String) { statusMessage = "GPS отключён" }
                }
                try {
                    location = locationManager.getLastKnownLocation(provider)
                    locationManager.requestLocationUpdates(provider, 3000L, 5f, listener, Looper.getMainLooper())
                    statusMessage = "GPS включён"
                } catch (_: SecurityException) { statusMessage = "Нет разрешения на GPS" }
                onDispose { locationManager.removeUpdates(listener) }
            }
        }
    }

    val pickup = activeOrder.point("pickup")
    val destination = activeOrder.point("destination")
    LaunchedEffect(activeOrder?.optString("id"), activeOrder?.optString("status"), pickup, destination, offlineSelected) {
        routeLine = emptyList()
        rerouteRequest = 0
        rerouteStart = null
        rerouteMessage = ""
        routeMessage = ""
        if (pickup != null && destination != null) {
            try {
                if (offlineSelected) {
                    val r = OfflineNavigation(context).route(pickup.latitude, pickup.longitude,
                        destination.latitude, destination.longitude)
                    routeLine = r.points.map { DriverPoint(it.latitude, it.longitude) }
                    routeMessage = "Офлайн-маршрут (предпросмотр): %.1f км, %d мин · не для расчёта тарифа".format(
                        java.util.Locale("ru", "RU"), r.meters / 1000, (r.seconds / 60).toInt())
                } else {
                    routeLine = fetchDriverRoute(pickup, destination)
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                routeMessage = e.message ?: "VEXA MAP: маршрут заказа недоступен"
            }
        }
    }
    // Explicit reroute after multiple trustworthy off-route fixes. Latest request wins.
    // Offline routing uses a locally installed road graph; no straight-line fallback.
    LaunchedEffect(rerouteRequest, activeOrder?.optString("id"), offlineSelected, pickup, destination) {
        if (rerouteRequest == 0) return@LaunchedEffect
        val start = rerouteStart ?: return@LaunchedEffect
        val orderStatus = activeOrder?.optString("status")?.lowercase().orEmpty()
        val target = if (orderStatus in setOf("in_progress", "started", "on_trip", "riding"))
            destination else pickup
        if (target == null) {
            rerouteMessage = "Неизвестна точка назначения для перестроения"
            return@LaunchedEffect
        }
        try {
            val updated = if (offlineSelected) {
                withContext(Dispatchers.IO) {
                    OfflineNavigation(context).route(start.latitude, start.longitude,
                        target.latitude, target.longitude).points.map { DriverPoint(it.latitude, it.longitude) }
                }
            } else fetchDriverRoute(start, target)
            if (updated.size < 2) throw IllegalStateException("Маршрут не содержит дорожную геометрию")
            routeLine = updated
            rerouteMessage = "Маршрут обновлён"
        } catch (error: Exception) {
            if (error is kotlinx.coroutines.CancellationException) throw error
            rerouteMessage = "Не удалось перестроить маршрут: ${error.message ?: "нет дорожного графа"}"
        }
    }
    LaunchedEffect(map, styleVersion, location, pickup, destination, routeLine, autoCenter, followDriver, perspective) {
        val active = map ?: return@LaunchedEffect
        active.clear()
        location?.let { active.addMarker(MarkerOptions().position(LatLng(it.latitude, it.longitude)).title("Вы здесь")) }
        pickup?.let { active.addMarker(MarkerOptions().position(LatLng(it.latitude, it.longitude)).title("Подача")) }
        destination?.let { active.addMarker(MarkerOptions().position(LatLng(it.latitude, it.longitude)).title("Назначение")) }
        if (routeLine.size > 1) {
            active.addPolyline(PolylineOptions().addAll(routeLine.map { LatLng(it.latitude, it.longitude) })
                .color(VexaDesign.brightRoute.toArgb()).width(5f))
        }
        // When GPS is available follow the car, not the pickup point; allow manual map inspection.
        val focus = location?.let { DriverPoint(it.latitude, it.longitude) } ?: pickup
        if (autoCenter && followDriver) focus?.let { active.animateCamera(CameraUpdateFactory.newCameraPosition(CameraPosition.Builder()
            .target(LatLng(it.latitude, it.longitude))
            .zoom(CameraMotion.zoomForSpeed(location?.takeIf { gps -> gps.hasSpeed() }?.speed?.toDouble() ?: 0.0,
                perspective == DriverMapPerspective.THREE_D))
            .tilt(NavigationCameraRules.driverTilt(perspective))
            .bearing(if (perspective == DriverMapPerspective.THREE_D && location?.hasBearing() == true)
                CameraMotion.bearing(active.cameraPosition.bearing, location!!.bearing.toDouble(), 0.45)
                else 0.0).build())) }
    }

    Box(modifier) {
        AndroidView(factory = { mapView }, modifier = Modifier.fillMaxSize())
        Column(modifier = Modifier.align(Alignment.TopStart).padding(8.dp), horizontalAlignment = Alignment.Start) {
            OutlinedButton(onClick = {
                mapMode = mapMode.next()
                OfflineMapMode.save(context, mapMode)
                recheck++
            }) { Text("Карта: ${mapMode.label}") }
            OutlinedButton(onClick = {
                perspective = perspective.next()
                DriverMapPreference.save(context, perspective)
            }) { Text("Навигация: ${perspective.label}") }
            OutlinedButton(onClick = { followDriver = !followDriver }) {
                Text(if (followDriver) "Слежение за машиной: вкл." else "Слежение: выкл.")
            }
            if (mapDataMessage.isNotBlank()) Surface(color = MaterialTheme.colorScheme.errorContainer) {
                Text(mapDataMessage, modifier = Modifier.padding(8.dp))
            }
            Button(onClick = {
                followDriver = true
                if (!permission) requestPermission.launch(arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION
                )) else location?.let {
                    map?.animateCamera(CameraUpdateFactory.newCameraPosition(CameraPosition.Builder()
                        .target(LatLng(it.latitude, it.longitude)).zoom(16.0)
                        .tilt(NavigationCameraRules.driverTilt(perspective))
                        .bearing(NavigationCameraRules.driverBearing(perspective,
                            it.takeIf { gps -> gps.hasBearing() }?.bearing?.toDouble())).build()))
                }
            }) { Text("Моя позиция") }
            Surface(color = MaterialTheme.colorScheme.surface) {
                Text(statusMessage, modifier = Modifier.padding(8.dp))
            }
            if (rerouteMessage.isNotBlank()) Surface(color = MaterialTheme.colorScheme.tertiaryContainer) {
                Text(rerouteMessage, modifier = Modifier.padding(8.dp))
            }
            if (routeMessage.isNotBlank()) Surface(color = MaterialTheme.colorScheme.errorContainer) {
                Text(routeMessage, modifier = Modifier.padding(8.dp))
            }
        }
    }
}
