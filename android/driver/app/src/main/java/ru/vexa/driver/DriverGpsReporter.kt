
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
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.platform.LocalContext
import java.util.concurrent.Executors

private val gpsExecutor = Executors.newSingleThreadExecutor()

@Composable
fun DriverGpsReporter(
    enabled: Boolean,
    onMessage: (String) -> Unit
) {
    val context = LocalContext.current
    val latestMessage = rememberUpdatedState(onMessage)

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val granted = permissions[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
            permissions[Manifest.permission.ACCESS_COARSE_LOCATION] == true

        if (granted) {
            requestOneDriverLocation(context) {
                latestMessage.value(it)
            }
        } else {
            latestMessage.value(
                "Разрешение на определение местоположения не предоставлено"
            )
        }
    }

    LaunchedEffect(enabled) {
        if (!enabled) return@LaunchedEffect

        val fineGranted = context.checkSelfPermission(
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        val coarseGranted = context.checkSelfPermission(
            Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        if (fineGranted || coarseGranted) {
            requestOneDriverLocation(context) {
                latestMessage.value(it)
            }
        } else {
            permissionLauncher.launch(
                arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION
                )
            )
        }
    }
}

private fun requestOneDriverLocation(
    context: Context,
    onMessage: (String) -> Unit
) {
    val locationManager = context.getSystemService(
        Context.LOCATION_SERVICE
    ) as LocationManager

    val fineGranted = context.checkSelfPermission(
        Manifest.permission.ACCESS_FINE_LOCATION
    ) == PackageManager.PERMISSION_GRANTED

    val coarseGranted = context.checkSelfPermission(
        Manifest.permission.ACCESS_COARSE_LOCATION
    ) == PackageManager.PERMISSION_GRANTED

    if (!fineGranted && !coarseGranted) {
        onMessage("Нет разрешения на получение GPS")
        return
    }

    val provider = when {
        fineGranted && locationManager.isProviderEnabled(
            LocationManager.GPS_PROVIDER
        ) -> LocationManager.GPS_PROVIDER

        locationManager.isProviderEnabled(
            LocationManager.NETWORK_PROVIDER
        ) -> LocationManager.NETWORK_PROVIDER

        else -> null
    }

    if (provider == null) {
        onMessage("Включите GPS или определение местоположения на телефоне")
        return
    }

    try {
        val lastLocation: Location? = locationManager.getLastKnownLocation(
            provider
        )

        if (lastLocation != null) {
            sendDriverLocation(lastLocation, onMessage)
            return
        }

        val listener = object : LocationListener {
            override fun onLocationChanged(location: Location) {
                try {
                    locationManager.removeUpdates(this)
                } catch (_: SecurityException) {
                }

                sendDriverLocation(location, onMessage)
            }

            @Deprecated("Deprecated by Android")
            override fun onStatusChanged(
                provider: String?,
                status: Int,
                extras: Bundle?
            ) {
            }

            override fun onProviderEnabled(provider: String) {
            }

            override fun onProviderDisabled(provider: String) {
            }
        }

        locationManager.requestLocationUpdates(
            provider,
            0L,
            0f,
            listener,
            Looper.getMainLooper()
        )

        onMessage("Определяем местоположение водителя...")

    } catch (e: SecurityException) {
        onMessage("Нет разрешения на доступ к местоположению")
    } catch (e: Exception) {
        onMessage(
            e.message ?: "Не удалось определить местоположение"
        )
    }
}

private fun sendDriverLocation(
    location: Location,
    onMessage: (String) -> Unit
) {
    gpsExecutor.execute {
        try {
            DriverApiClient.sendLocation(
                latitude = location.latitude,
                longitude = location.longitude,
                accuracyMeters = if (location.hasAccuracy()) {
                    location.accuracy.toDouble()
                } else {
                    null
                }
            )

            onMessage("Местоположение передано диспетчеру")
        } catch (e: Exception) {
            onMessage(
                e.message ?: "Не удалось передать координаты на сервер"
            )
        }
    }
}
