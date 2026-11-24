package ru.vexa.driver

import androidx.activity.compose.BackHandler
import ru.vexa.offline.OfflineMapsScreen
import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat

private val themeNames = listOf("system" to "Авто", "light" to "День", "dark" to "Ночь")
private val soundNames = listOf(
    "classic" to "Классика", "modern" to "Модерн", "soft" to "Мягкий",
    "dynamic" to "Динамичный", "calm" to "Спокойный", "premium" to "Премиум"
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun DriverSettingsScreen(
    value: DriverPreferences.State,
    onValueChange: (DriverPreferences.State) -> Unit,
    onBack: () -> Unit,
    onLogout: () -> Unit,
    driverName: String,
    phone: String,
    cityName: String,
    vehicleDescription: String
) {
    var offlineMapsOpen by remember { mutableStateOf(false) }
    if (offlineMapsOpen) {
        BackHandler { offlineMapsOpen = false }
        OfflineMapsScreen(
            mapBaseUrl = BuildConfig.VEXA_MAP_BASE_URL,
            allowDebugHttp = BuildConfig.DEBUG,
            onBack = { offlineMapsOpen = false }
        )
        return
    }
    val context = LocalContext.current
    var notificationGranted by remember {
        mutableStateOf(Build.VERSION.SDK_INT < 33 ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED)
    }
    val notificationLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        notificationGranted = granted
    }
    val locationGranted = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
    fun openAppSettings() {
        context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
            Uri.fromParts("package", context.packageName, null)))
    }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Настройки водителя", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Вернуться к заказам")
                    }
                }
            )
        }
    ) { insets ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(insets).padding(horizontal = 16.dp),
            contentPadding = PaddingValues(bottom = 28.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item {
                SettingsCard("Профиль") {
                    Text(driverName, fontWeight = FontWeight.Bold, fontSize = 17.sp)
                    if (phone.isNotBlank()) Text(phone)
                    Text("Город: $cityName")
                    if (vehicleDescription.isNotBlank()) Text(vehicleDescription)
                    TextButton(onClick = onLogout) { Text("Выйти из аккаунта") }
                }
            }
            item {
                SettingsCard("Внешний вид") {
                    Text("Тема приложения")
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        themeNames.forEach { (code, label) ->
                            FilterChip(
                                selected = value.theme == code,
                                onClick = { onValueChange(value.copy(theme = code)) },
                                label = { Text(label) }
                            )
                        }
                    }
                    Text("Тема сохраняется после перезапуска.", style = MaterialTheme.typography.bodySmall)
                }
            }
            item {
                SettingsCard("Новые заказы") {
                    SettingsToggle("Звуковые оповещения", value.alertsEnabled) {
                        onValueChange(value.copy(alertsEnabled = it))
                    }
                    Text("Звуковой профиль")
                    soundNames.chunked(2).forEach { row ->
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            row.forEach { (code, label) ->
                                FilterChip(
                                    selected = value.soundProfile == code,
                                    onClick = { onValueChange(value.copy(soundProfile = code)) },
                                    enabled = value.alertsEnabled,
                                    label = { Text(label) }
                                )
                            }
                        }
                    }
                    Text("Громкость звука: ${value.volume}%")
                    Slider(
                        value = value.volume.toFloat(),
                        onValueChange = { onValueChange(value.copy(volume = it.toInt().coerceIn(0,100))) },
                        valueRange = 0f..100f,
                        steps = 9,
                        enabled = value.alertsEnabled
                    )
                    SettingsToggle("Вибрация", value.vibrationEnabled, value.alertsEnabled) {
                        onValueChange(value.copy(vibrationEnabled = it))
                    }
                    OutlinedButton(
                        onClick = { DriverOfferAlerts.preview(context, value) },
                        enabled = value.alertsEnabled
                    ) { Text("Проверить сигнал") }
                    Text(
                        "Сигнал звучит один раз для нового предложения. Режим без звука и ограничения Android имеют приоритет.",
                        style = MaterialTheme.typography.bodySmall
                    )
                    if (Build.VERSION.SDK_INT >= 33 && !notificationGranted) {
                        Text("Системные уведомления не разрешены: в фоне карточка нового заказа может не появиться.",
                            color = MaterialTheme.colorScheme.error)
                        OutlinedButton(onClick = {
                            notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                        }) { Text("Разрешить уведомления") }
                    }
                }
            }
            item {
                SettingsCard("Навигация VEXA MAP") {
                    Button(onClick = { offlineMapsOpen = true }) {
                        Text("Офлайн-карты · округа России")
                    }

                    SettingsToggle("Следовать за GPS на карте", value.followGps) {
                        onValueChange(value.copy(followGps = it))
                    }
                    Text("Маршруты строятся сервисом VEXA MAP; загрузка карт и маршрутов требует подготовленных геоданных.",
                        style = MaterialTheme.typography.bodySmall)
                }
            }
            item {
                SettingsCard("Геолокация и безопасность") {
                    Text(if (locationGranted) "Доступ к местоположению разрешён" else "Доступ к местоположению не предоставлен")
                    OutlinedButton(onClick = ::openAppSettings) { Text("Разрешения Android") }
                    Text("Пароли и токены не показываются. Выход удаляет сохранённую сессию на устройстве.",
                        style = MaterialTheme.typography.bodySmall)
                }
            }
            item {
                SettingsCard("О приложении") {
                    Text("VEXA Driver · ${BuildConfig.VERSION_NAME}")
                    Text("VEXA MAP · MapLibre", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
private fun SettingsCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(title, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary, fontSize = 18.sp)
            content()
        }
    }
}

@Composable
private fun SettingsToggle(title: String, checked: Boolean, enabled: Boolean = true, onChange: (Boolean) -> Unit) {
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(title, modifier = Modifier.weight(1f))
        Switch(checked = checked, onCheckedChange = onChange, enabled = enabled)
    }
}
