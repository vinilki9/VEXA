package ru.vexa.client

import androidx.activity.compose.BackHandler
import ru.vexa.offline.OfflineMapsScreen
import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner

private fun locationEnabled(context: android.content.Context): Boolean =
    ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) ==
        PackageManager.PERMISSION_GRANTED ||
    ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) ==
        PackageManager.PERMISSION_GRANTED

/** Full-screen settings page. Features without real implementations (push notifications,
 * online card processing, language packs, account deletion) are intentionally omitted. */
@Composable
fun VexaClientSettingsScreen(
    themeMode: VexaThemeMode,
    onThemeModeChange: (VexaThemeMode) -> Unit,
    defaultPayment: String,
    onDefaultPaymentChange: (String) -> Unit,
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    var authorized by remember { mutableStateOf(!ApiClient.getAccessToken().isNullOrBlank()) }
    var showLogin by remember { mutableStateOf(false) }
    var confirmLogout by remember { mutableStateOf(false) }
    var confirmClearPlaces by remember { mutableStateOf(false) }
    var privacyMessage by remember { mutableStateOf("") }
    var sessionError by remember { mutableStateOf<String?>(null) }
    var paymentMenu by remember { mutableStateOf(false) }
    var offlineMapsOpen by remember { mutableStateOf(false) }
    var locationGranted by remember { mutableStateOf(locationEnabled(context)) }

    // Refresh the permission indicator after returning from Android system settings.
    DisposableEffect(owner, context) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                locationGranted = locationEnabled(context)
            }
        }
        owner.lifecycle.addObserver(observer)
        onDispose { owner.lifecycle.removeObserver(observer) }
    }

    if (offlineMapsOpen) {
        BackHandler { offlineMapsOpen = false }
        OfflineMapsScreen(
            mapBaseUrl = BuildConfig.VEXA_MAP_BASE_URL,
            allowDebugHttp = BuildConfig.DEBUG,
            onBack = { offlineMapsOpen = false }
        )
        return
    }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(modifier = Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Назад к карте")
                }
                Text("Настройки", style = MaterialTheme.typography.headlineSmall)
            }
            HorizontalDivider()
            Column(
                modifier = Modifier.fillMaxWidth().weight(1f)
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 16.dp, vertical = 16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                SettingsSection(title = "Профиль") {
                    Text(
                        if (authorized) "Вы вошли как ${ApiClient.getPassengerPhone().orEmpty()}"
                        else "Войдите, чтобы оформлять заказы и видеть их состояние.",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Spacer(Modifier.height(8.dp))
                    if (authorized) {
                        OutlinedButton(onClick = { confirmLogout = true }) { Text("Выйти из профиля") }
                    } else {
                        Button(onClick = { showLogin = true }) { Text("Войти по номеру телефона") }
                    }
                    sessionError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                }

                SettingsSection(title = "Внешний вид") {
                    Text("Тема приложения", style = MaterialTheme.typography.titleSmall)
                    val choices = listOf(
                        VexaThemeMode.SYSTEM to "Как на устройстве",
                        VexaThemeMode.LIGHT to "Светлая",
                        VexaThemeMode.DARK to "Тёмная"
                    )
                    choices.forEach { (mode, label) ->
                        Row(
                            modifier = Modifier.fillMaxWidth()
                                .clickable { onThemeModeChange(mode) }
                                .padding(vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            RadioButton(
                                selected = themeMode == mode,
                                onClick = { onThemeModeChange(mode) }
                            )
                            Text(label)
                        }
                    }
                }

                SettingsSection(title = "Заказы и оплата") {
                    Text("Способ оплаты по умолчанию", style = MaterialTheme.typography.titleSmall)
                    Spacer(Modifier.height(8.dp))
                    Box {
                        OutlinedButton(onClick = { paymentMenu = true }) {
                            Text("$defaultPayment  ▾")
                        }
                        DropdownMenu(
                            expanded = paymentMenu,
                            onDismissRequest = { paymentMenu = false }
                        ) {
                            VexaClientPreferences.paymentMethods.forEach { method ->
                                DropdownMenuItem(
                                    text = { Text(method) },
                                    onClick = {
                                        onDefaultPaymentChange(method)
                                        paymentMenu = false
                                    }
                                )
                            }
                        }
                    }
                    Text(
                        "Это предварительный выбор при создании заказа. " +
                            "Доступность безналичной оплаты зависит от подключения платёжного сервиса.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                SettingsSection(title = "Карта и геопозиция") {
                    Button(onClick = { offlineMapsOpen = true }) {
                        Text("Офлайн-карты России · скачать и обновить")
                    }

                    Text(
                        if (locationGranted) "Доступ к геопозиции разрешён"
                        else "Доступ к геопозиции не предоставлен",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedButton(
                        onClick = {
                            val intent = Intent(
                                Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                Uri.parse("package:${context.packageName}")
                            )
                            context.startActivity(intent)
                        }
                    ) {
                        Text("Разрешения приложения в Android")
                    }
                    Text(
                        "Геопозиция нужна для выбора места подачи. " +
                            "VEXA MAP использует карту, настроенную для данного сервера.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                SettingsSection(title = "Конфиденциальность") {
                    Text("Дом и Работа хранятся на устройстве для текущего профиля. " +
                         "Другие аккаунты не видят эти адреса.",
                         style = MaterialTheme.typography.bodySmall)
                    OutlinedButton(
                        onClick = { confirmClearPlaces = true },
                        enabled = authorized
                    ) { Text("Удалить мои сохранённые адреса") }
                    if (privacyMessage.isNotBlank()) {
                        Text(privacyMessage, style = MaterialTheme.typography.bodySmall)
                    }
                }

                SettingsSection(title = "О приложении") {
                    Text("VEXA Client · версия ${BuildConfig.VERSION_NAME}")
                    Text("Карта: VEXA MAP / MapLibre", style = MaterialTheme.typography.bodySmall)
                    Text(
                        "Настройки сохраняются на этом устройстве. " +
                            "Токен входа хранится отдельно в защищённом хранилище Android.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }

    if (confirmClearPlaces) {
        AlertDialog(
            onDismissRequest = { confirmClearPlaces = false },
            title = { Text("Удалить сохранённые адреса?") },
            text = { Text("Дом и Работа будут удалены только из этого профиля на устройстве. Поездки на сервере не затрагиваются.") },
            confirmButton = {
                TextButton(onClick = {
                    VexaSavedPlaces.clearCurrentAccount(context)
                    privacyMessage = "Адреса удалены."
                    confirmClearPlaces = false
                }) { Text("Удалить") }
            },
            dismissButton = {
                TextButton(onClick = { confirmClearPlaces = false }) { Text("Отмена") }
            }
        )
    }
    if (showLogin) {
        PassengerAuthDialog(
            onAuthenticated = {
                authorized = true
                sessionError = null
                showLogin = false
            },
            onDismiss = { showLogin = false }
        )
    }
    if (confirmLogout) {
        AlertDialog(
            onDismissRequest = { confirmLogout = false },
            title = { Text("Выйти из VEXA?") },
            text = { Text("Сессия будет удалена с этого устройства. Созданные заказы на сервере сохранятся.") },
            confirmButton = {
                TextButton(onClick = {
                    try {
                        ApiClient.clearAccessToken()
                        authorized = false
                        sessionError = null
                    } catch (error: Exception) {
                        sessionError = "Не удалось полностью очистить сохранённую сессию. Повторите попытку."
                    } finally {
                        confirmLogout = false
                    }
                }) { Text("Выйти") }
            },
            dismissButton = {
                TextButton(onClick = { confirmLogout = false }) { Text("Отмена") }
            }
        )
    }
}

@Composable
private fun SettingsSection(title: String, content: @Composable () -> Unit) {
    Card(shape = RoundedCornerShape(18.dp), modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.height(4.dp))
            content()
        }
    }
}
