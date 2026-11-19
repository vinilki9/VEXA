
package ru.vexa.driver

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

private const val PROFILE_REFRESH_INTERVAL_MS = 15_000L

@Composable
fun DriverGpsReporter(
    enabled: Boolean,
    onMessage: (String) -> Unit
) {
    val context = LocalContext.current
    val appContext = context.applicationContext
    val latestMessage = rememberUpdatedState(onMessage)

    fun hasLocationPermission(): Boolean {
        val fineGranted = appContext.checkSelfPermission(
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        val coarseGranted = appContext.checkSelfPermission(
            Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        return fineGranted || coarseGranted
    }

    var locationPermissionGranted by remember {
        mutableStateOf(hasLocationPermission())
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val granted =
            permissions[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
            permissions[Manifest.permission.ACCESS_COARSE_LOCATION] == true

        locationPermissionGranted = granted

        if (!granted) {
            DriverLocationService.stop(appContext)
            latestMessage.value(
                "Разрешение на определение местоположения не предоставлено"
            )
        }
    }

    LaunchedEffect(enabled, locationPermissionGranted) {
        if (!enabled) {
            DriverLocationService.stop(appContext)
            return@LaunchedEffect
        }

        if (!locationPermissionGranted) {
            permissionLauncher.launch(
                arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION
                )
            )
            return@LaunchedEffect
        }

        var lastOnlineState: Boolean? = null
        var lastReportedMessage = ""

        fun reportMessage(message: String) {
            if (message != lastReportedMessage) {
                lastReportedMessage = message
                latestMessage.value(message)
            }
        }

        while (true) {
            try {
                val profile = withContext(Dispatchers.IO) {
                    DriverApiClient.getProfile()
                }

                val isOnline = profile.optBoolean(
                    "is_online",
                    false
                )

                if (lastOnlineState != isOnline) {
                    if (isOnline) {
                        DriverLocationService.start(appContext)
                        reportMessage(
                            "Вы на линии. Фоновая передача GPS включена"
                        )
                    } else {
                        DriverLocationService.stop(appContext)
                        reportMessage(
                            "Вы не на линии. Передача GPS остановлена"
                        )
                    }

                    lastOnlineState = isOnline
                }

            } catch (e: DriverApiHttpException) {
                if (e.statusCode == 401 || e.statusCode == 403) {
                    DriverLocationService.stop(appContext)
                    lastOnlineState = false

                    reportMessage(
                        "Ошибка авторизации. Войдите в профиль водителя повторно"
                    )
                } else {
                    reportMessage(
                        "Не удалось проверить статус водителя. " +
                            "Повторная проверка будет выполнена автоматически"
                    )
                }
            } catch (e: Exception) {
                reportMessage(
                    "Нет связи с сервером. Проверка режима водителя " +
                        "будет повторена автоматически"
                )
            }

            delay(PROFILE_REFRESH_INTERVAL_MS)
        }
    }
}
