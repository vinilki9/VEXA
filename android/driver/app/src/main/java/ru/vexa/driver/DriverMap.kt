
package ru.vexa.driver

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.launch
import ru.dgis.sdk.Duration
import ru.dgis.sdk.compose.map.MapComposable
import ru.dgis.sdk.coordinates.GeoPoint
import ru.dgis.sdk.coordinates.Latitude
import ru.dgis.sdk.coordinates.Longitude
import ru.dgis.sdk.geometry.Elevation
import ru.dgis.sdk.geometry.GeoPointWithElevation
import ru.dgis.sdk.map.*

private const val OBOLENSK_LATITUDE = 54.9770
private const val OBOLENSK_LONGITUDE = 37.2280

@Composable
fun DriverMap(
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val application = context.applicationContext as VexaApplication
    val sdkContext = application.sdkContext
    val coroutineScope = rememberCoroutineScope()

    val mapViewModel = remember {
        DefaultMapControllerViewModel(
            sdkContext,
            MapControllerOptions(
                position = CameraPosition(
                    point = GeoPoint(
                        OBOLENSK_LATITUDE,
                        OBOLENSK_LONGITUDE
                    ),
                    zoom = Zoom(14.0f)
                )
            )
        )
    }

    var dgisMap by remember {
        mutableStateOf<ru.dgis.sdk.map.Map?>(null)
    }

    var mapObjectManager by remember {
        mutableStateOf<MapObjectManager?>(null)
    }

    var currentLocation by remember {
        mutableStateOf<Location?>(null)
    }

    var locationMessage by remember {
        mutableStateOf("Определяем местоположение...")
    }

    var permissionGranted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) == PackageManager.PERMISSION_GRANTED ||
                ContextCompat.checkSelfPermission(
                    context,
                    Manifest.permission.ACCESS_COARSE_LOCATION
                ) == PackageManager.PERMISSION_GRANTED
        )
    }

    val permissionLauncher =
        rememberLauncherForActivityResult(
            ActivityResultContracts.RequestMultiplePermissions()
        ) { permissions ->
            permissionGranted =
                permissions[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
                    permissions[Manifest.permission.ACCESS_COARSE_LOCATION] == true
        }

    LaunchedEffect(mapViewModel) {
        try {
            val map = mapViewModel.awaitMap()
            dgisMap = map
            mapObjectManager = MapObjectManager(map)
        } catch (error: Exception) {
            locationMessage = "Не удалось загрузить карту 2ГИС"
        }
    }

    LaunchedEffect(permissionGranted, dgisMap) {
        if (dgisMap == null) return@LaunchedEffect

        if (!permissionGranted) {
            locationMessage = "Разрешите доступ к местоположению"
            return@LaunchedEffect
        }

        val locationManager =
            context.getSystemService(Context.LOCATION_SERVICE) as LocationManager

        val provider = when {
            locationManager.isProviderEnabled(
                LocationManager.GPS_PROVIDER
            ) -> LocationManager.GPS_PROVIDER

            locationManager.isProviderEnabled(
                LocationManager.NETWORK_PROVIDER
            ) -> LocationManager.NETWORK_PROVIDER

            else -> null
        }

        if (provider == null) {
            locationMessage = "Включите GPS на телефоне"
            return@LaunchedEffect
        }

        try {
            val lastKnown = locationManager.getLastKnownLocation(provider)

            if (lastKnown != null) {
                currentLocation = lastKnown
                locationMessage = "Местоположение определено"
            } else {
                locationMessage = "Ожидаем сигнал GPS"
            }
        } catch (_: SecurityException) {
            locationMessage = "Нет разрешения на GPS"
        }
    }

    LaunchedEffect(currentLocation, mapObjectManager) {
        val location = currentLocation ?: return@LaunchedEffect
        val manager = mapObjectManager ?: return@LaunchedEffect

        manager.removeAll()

        manager.addObject(
            Marker(
                MarkerOptions(
                    position = GeoPointWithElevation(
                        latitude = Latitude(value = location.latitude),
                        longitude = Longitude(value = location.longitude),
                        elevation = Elevation(value = 0.0f)
                    ),
                    text = "Вы здесь"
                )
            )
        )
    }

    DisposableEffect(mapViewModel) {
        onDispose {
            mapObjectManager?.removeAll()
            mapObjectManager = null
            dgisMap = null
            mapViewModel.close()
        }
    }

    Box(modifier = modifier) {
        MapComposable(
            modifier = Modifier.fillMaxSize(),
            viewModel = mapViewModel,
            renderOptions = MapRenderOptions(),
            copyrightOptions = MapCopyrightOptions()
        )

        Column(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(12.dp),
            horizontalAlignment = Alignment.End
        ) {
            Button(
                onClick = {
                    if (!permissionGranted) {
                        permissionLauncher.launch(
                            arrayOf(
                                Manifest.permission.ACCESS_FINE_LOCATION,
                                Manifest.permission.ACCESS_COARSE_LOCATION
                            )
                        )
                    } else {
                        val location = currentLocation

                        if (location != null) {
                            dgisMap?.camera?.move(
                                CameraPosition(
                                    point = GeoPoint(
                                        location.latitude,
                                        location.longitude
                                    ),
                                    zoom = Zoom(16.0f)
                                ),
                                Duration.ofMilliseconds(700),
                                CameraAnimationType.DEFAULT
                            )
                        } else {
                            locationMessage = "Местоположение пока не определено"
                        }
                    }
                }
            ) {
                Text("Моё местоположение")
            }

            Surface(
                color = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f),
                shape = MaterialTheme.shapes.small
            ) {
                Text(
                    text = locationMessage,
                    modifier = Modifier.padding(
                        horizontal = 10.dp,
                        vertical = 6.dp
                    ),
                    style = MaterialTheme.typography.labelSmall
                )
            }
        }
    }
}
