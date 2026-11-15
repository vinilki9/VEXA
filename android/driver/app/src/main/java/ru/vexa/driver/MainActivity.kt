
package ru.vexa.driver

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import java.util.concurrent.Executors

private val Teal = Color(0xFF20C6B7)
private val Ink = Color(0xFF111827)
private val Navy = Color(0xFF1E293B)

private val apiExecutor = Executors.newSingleThreadExecutor()
private val mainHandler = Handler(Looper.getMainLooper())

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            DriverScreen()
        }
    }
}

private fun runApiCall(
    action: () -> Any?,
    onResult: (Any?, String?) -> Unit
) {
    apiExecutor.execute {
        try {
            val result = action()
            mainHandler.post {
                onResult(result, null)
            }
        } catch (e: Exception) {
            mainHandler.post {
                onResult(null, e.message ?: "Ошибка соединения с сервером")
            }
        }
    }
}

@Composable
fun DriverScreen() {
    var login by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }

    var authorized by remember {
        mutableStateOf(DriverApiClient.getAccessToken() != null)
    }

    var loading by remember { mutableStateOf(false) }
    var online by remember { mutableStateOf(false) }

    var driverName by remember { mutableStateOf("Водитель") }
    var phone by remember { mutableStateOf("") }
    var cityName by remember { mutableStateOf("Оболенск") }
    var branchName by remember { mutableStateOf("") }
    var rating by remember { mutableStateOf("") }
    var vehicleDescription by remember { mutableStateOf("") }

    var orders by remember { mutableStateOf(listOf<JSONObject>()) }

    var errorMessage by remember { mutableStateOf("") }
    var infoMessage by remember { mutableStateOf("") }

    DriverGpsReporter(
        enabled = authorized,
        onMessage = { message ->
            infoMessage = message
        }
    )

    var theme by remember { mutableStateOf("Системная") }
    var sound by remember { mutableStateOf("classic") }

    val dark = theme == "Ночная" ||
        (theme == "Системная" && isSystemInDarkTheme())

    val bg = if (dark) Ink else Color(0xFFF5F7FA)
    val fg = if (dark) Color.White else Ink
    val cardColor = if (dark) Navy else Color.White

    fun loadDriverData() {
        loading = true
        errorMessage = ""

        runApiCall(
            action = {
                val profile = DriverApiClient.getProfile()
                val activeOrders = DriverApiClient.getActiveOrders()

                Pair(profile, activeOrders)
            },
            onResult = { result, error ->
                loading = false

                if (error != null) {
                    errorMessage = error
                    return@runApiCall
                }

                val data = result as Pair<*, *>
                val profile = data.first as JSONObject
                val activeOrders = data.second as JSONObject

                driverName = profile.optString(
                    "username",
                    "Водитель"
                )

                phone = profile.optString("phone", "")
                online = profile.optBoolean("is_online", false)
                rating = profile.optString("rating", "")

                cityName = profile
                    .optJSONObject("city")
                    ?.optString("name", "Оболенск")
                    ?: "Оболенск"

                branchName = profile
                    .optJSONObject("branch")
                    ?.optString("name", "")
                    ?: ""

                val vehicles = profile.optJSONArray("vehicles")
                vehicleDescription = if (
                    vehicles != null && vehicles.length() > 0
                ) {
                    val vehicle = vehicles.getJSONObject(0)

                    listOf(
                        vehicle.optString("make"),
                        vehicle.optString("model"),
                        vehicle.optString("color"),
                        vehicle.optString("license_plate")
                    ).filter { it.isNotBlank() }
                        .joinToString(" · ")
                } else {
                    "Автомобиль не указан"
                }

                val orderArray = activeOrders.optJSONArray("orders")
                val loadedOrders = mutableListOf<JSONObject>()

                if (orderArray != null) {
                    for (i in 0 until orderArray.length()) {
                        loadedOrders.add(orderArray.getJSONObject(i))
                    }
                }

                orders = loadedOrders
                authorized = true
                infoMessage = "Данные водителя обновлены"
            }
        )
    }

    fun changeOnlineStatus(value: Boolean) {
        if (loading) return

        loading = true
        errorMessage = ""

        runApiCall(
            action = {
                DriverApiClient.setOnline(value)
            },
            onResult = { result, error ->
                loading = false

                if (error != null) {
                    errorMessage = error
                    return@runApiCall
                }

                val response = result as JSONObject
                online = response.optBoolean("is_online", value)

                infoMessage = if (online) {
                    "Вы вышли на линию"
                } else {
                    "Вы сняты с линии"
                }

                if (online) {
                    loadDriverData()
                }
            }
        )
    }

    fun refreshOrders() {
        loading = true
        errorMessage = ""

        runApiCall(
            action = {
                DriverApiClient.getActiveOrders()
            },
            onResult = { result, error ->
                loading = false

                if (error != null) {
                    errorMessage = error
                    return@runApiCall
                }

                val response = result as JSONObject
                val array = response.optJSONArray("orders")
                val updated = mutableListOf<JSONObject>()

                if (array != null) {
                    for (i in 0 until array.length()) {
                        updated.add(array.getJSONObject(i))
                    }
                }

                orders = updated
                infoMessage = "Список заказов обновлён"
            }
        )
    }

    fun advanceOrder(order: JSONObject) {
        val orderId = order.optString("id")
        val currentStatus = order.optString("status")

        val nextStatus = when (currentStatus) {
            "assigned" -> "arrived"
            "arrived" -> "in_progress"
            "in_progress" -> "completed"
            else -> return
        }

        loading = true
        errorMessage = ""

        runApiCall(
            action = {
                DriverApiClient.updateOrderStatus(
                    orderId = orderId,
                    status = nextStatus
                )
            },
            onResult = { _, error ->
                loading = false

                if (error != null) {
                    errorMessage = error
                } else {
                    infoMessage = "Статус заказа обновлён"
                    refreshOrders()
                }
            }
        )
    }

    Surface(
        color = bg,
        modifier = Modifier.fillMaxSize()
    ) {
        if (!authorized) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(24.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    "VEXA",
                    color = Teal,
                    fontSize = 34.sp
                )

                Text(
                    "ВОДИТЕЛЬ",
                    color = fg,
                    fontSize = 16.sp
                )

                Spacer(Modifier.height(28.dp))

                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = cardColor
                    ),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier.padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        Text(
                            "Вход водителя",
                            color = fg,
                            style = MaterialTheme.typography.titleLarge
                        )

                        OutlinedTextField(
                            value = login,
                            onValueChange = { login = it },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Логин или телефон") },
                            singleLine = true,
                            enabled = !loading
                        )

                        OutlinedTextField(
                            value = password,
                            onValueChange = { password = it },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Пароль") },
                            singleLine = true,
                            enabled = !loading,
                            visualTransformation = PasswordVisualTransformation(),
                            keyboardOptions = KeyboardOptions(
                                keyboardType = KeyboardType.Password
                            )
                        )

                        if (errorMessage.isNotBlank()) {
                            Text(
                                errorMessage,
                                color = MaterialTheme.colorScheme.error
                            )
                        }

                        Button(
                            onClick = {
                                if (login.isBlank() || password.isBlank()) {
                                    errorMessage = "Введите логин и пароль"
                                    return@Button
                                }

                                loading = true
                                errorMessage = ""

                                runApiCall(
                                    action = {
                                        DriverApiClient.login(
                                            login.trim(),
                                            password
                                        )
                                        DriverApiClient.getProfile()
                                        DriverApiClient.getActiveOrders()
                                    },
                                    onResult = { _, error ->
                                        loading = false

                                        if (error != null) {
                                            DriverApiClient.clearAccessToken()
                                            errorMessage = error
                                        } else {
                                            password = ""
                                            loadDriverData()
                                        }
                                    }
                                )
                            },
                            modifier = Modifier.fillMaxWidth(),
                            enabled = !loading,
                            colors = ButtonDefaults.buttonColors(
                                containerColor = Teal
                            )
                        ) {
                            Text(
                                if (loading) "Подключение..." else "Войти",
                                color = Ink
                            )
                        }

                        Text(
                            "Сервер VEXA: 109.120.184.20",
                            color = Color.Gray,
                            fontSize = 11.sp
                        )
                    }
                }
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 18.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
                contentPadding = PaddingValues(vertical = 20.dp)
            ) {
                item {
                    Row(
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            "VEXA",
                            color = Teal,
                            fontSize = 25.sp
                        )

                        Spacer(Modifier.width(10.dp))

                        Text(
                            "ВОДИТЕЛЬ",
                            color = fg
                        )

                        Spacer(Modifier.weight(1f))

                        TextButton(
                            onClick = {
                                DriverApiClient.clearAccessToken()
                                authorized = false
                                online = false
                                orders = emptyList()
                                errorMessage = ""
                                infoMessage = "Вы вышли из профиля"
                            }
                        ) {
                            Text("Выйти")
                        }
                    }
                }

                item {
                    Card(
                        colors = CardDefaults.cardColors(
                            containerColor = cardColor
                        ),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(
                            modifier = Modifier.padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(7.dp)
                        ) {
                            Text(
                                driverName,
                                color = fg,
                                style = MaterialTheme.typography.titleLarge
                            )

                            if (phone.isNotBlank()) {
                                Text(phone, color = fg)
                            }

                            Text(
                                "Город: $cityName",
                                color = fg
                            )

                            if (branchName.isNotBlank()) {
                                Text(
                                    "Филиал: $branchName",
                                    color = fg
                                )
                            }

                            if (rating.isNotBlank()) {
                                Text(
                                    "Рейтинг: $rating",
                                    color = fg
                                )
                            }

                            Text(
                                vehicleDescription,
                                color = fg,
                                fontSize = 12.sp
                            )
                        }
                    }
                }

                item {
                    Card(
                        colors = CardDefaults.cardColors(
                            containerColor = cardColor
                        ),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(
                                modifier = Modifier.weight(1f)
                            ) {
                                Text(
                                    if (online) "На линии" else "Не на линии",
                                    color = fg,
                                    style = MaterialTheme.typography.titleMedium
                                )

                                Text(
                                    if (online) {
                                        "Вы доступны для распределения заказов"
                                    } else {
                                        "Вы не получаете новые назначения"
                                    },
                                    color = Color.Gray,
                                    fontSize = 11.sp
                                )
                            }

                            Switch(
                                checked = online,
                                onCheckedChange = { changeOnlineStatus(it) },
                                enabled = !loading,
                                colors = SwitchDefaults.colors(
                                    checkedThumbColor = Teal,
                                    checkedTrackColor = Teal.copy(alpha = 0.4f)
                                )
                            )
                        }
                    }
                }

                item {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(145.dp)
                            .background(
                                if (dark) Navy else Color(0xFFDDEBE8),
                                RoundedCornerShape(18.dp)
                            )
                            .padding(16.dp)
                    ) {
                        Column(
                            verticalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            Text(
                                "VEXA · ОБОЛЕНСК",
                                color = if (dark) Teal else Color(0xFF46716D),
                                fontSize = 12.sp
                            )

                            Text(
                                "Карта и GPS",
                                color = fg,
                                style = MaterialTheme.typography.titleMedium
                            )

                            Text(
                                "Отображение карты и передача GPS будут подключены отдельным этапом.",
                                color = fg,
                                fontSize = 11.sp
                            )
                        }
                    }
                }

                item {
                    Row(
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            "Активные заказы",
                            color = fg,
                            style = MaterialTheme.typography.titleLarge
                        )

                        Spacer(Modifier.weight(1f))

                        TextButton(
                            onClick = { refreshOrders() },
                            enabled = !loading
                        ) {
                            Text("Обновить")
                        }
                    }
                }

                if (orders.isEmpty()) {
                    item {
                        Card(
                            colors = CardDefaults.cardColors(
                                containerColor = cardColor
                            ),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                "Активных заказов нет",
                                color = fg,
                                modifier = Modifier.padding(18.dp)
                            )
                        }
                    }
                } else {
                    items(
                        items = orders,
                        key = { it.optString("id") }
                    ) { order ->
                        val pickup = order
                            .optJSONObject("pickup")
                            ?.optString("address", "Не указан")
                            ?: "Не указан"

                        val destination = order
                            .optJSONObject("destination")
                            ?.optString("address", "Не указан")
                            ?: "Не указан"

                        val status = order.optString("status")
                        val orderNumber = order.optString(
                            "public_number",
                            order.optString("id")
                        )

                        val statusText = when (status) {
                            "assigned" -> "Водитель назначен"
                            "arrived" -> "Водитель на месте"
                            "in_progress" -> "Поездка выполняется"
                            else -> status
                        }

                        val nextAction = when (status) {
                            "assigned" -> "Я на месте"
                            "arrived" -> "Начать поездку"
                            "in_progress" -> "Завершить поездку"
                            else -> null
                        }

                        Card(
                            colors = CardDefaults.cardColors(
                                containerColor = cardColor
                            ),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Column(
                                modifier = Modifier.padding(16.dp),
                                verticalArrangement = Arrangement.spacedBy(9.dp)
                            ) {
                                Text(
                                    "Заказ № $orderNumber",
                                    color = Teal,
                                    style = MaterialTheme.typography.titleMedium
                                )

                                Text(
                                    statusText,
                                    color = fg
                                )

                                Text(
                                    "Подача: $pickup",
                                    color = fg
                                )

                                Text(
                                    "Назначение: $destination",
                                    color = fg
                                )

                                val price = order.optString("price_rub", "")
                                if (price.isNotBlank() && price != "null") {
                                    Text(
                                        "Стоимость: $price ₽",
                                        color = fg
                                    )
                                }

                                if (nextAction != null) {
                                    Button(
                                        onClick = { advanceOrder(order) },
                                        enabled = !loading,
                                        colors = ButtonDefaults.buttonColors(
                                            containerColor = Teal
                                        ),
                                        modifier = Modifier.fillMaxWidth()
                                    ) {
                                        Text(
                                            nextAction,
                                            color = Ink
                                        )
                                    }
                                }
                            }
                        }
                    }
                }

                item {
                    Text(
                        "Тема приложения",
                        color = fg
                    )

                    Row(
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        listOf(
                            "Дневная",
                            "Ночная",
                            "Системная"
                        ).forEach {
                            FilterChip(
                                selected = theme == it,
                                onClick = { theme = it },
                                label = { Text(it) },
                                colors = FilterChipDefaults.filterChipColors(
                                    selectedContainerColor = Teal.copy(alpha = 0.2f)
                                )
                            )
                        }
                    }
                }

                item {
                    Text(
                        "Звуковой профиль",
                        color = fg
                    )

                    Row(
                        horizontalArrangement = Arrangement.spacedBy(5.dp)
                    ) {
                        listOf(
                            "classic",
                            "modern",
                            "soft",
                            "dynamic",
                            "calm",
                            "premium"
                        ).forEach {
                            FilterChip(
                                selected = sound == it,
                                onClick = { sound = it },
                                label = {
                                    Text(it, fontSize = 9.sp)
                                }
                            )
                        }
                    }
                }

                item {
                    Text(
                        "Голосовые команды: «Принять», «Маршрут», «Диспетчер»",
                        color = fg,
                        fontSize = 11.sp
                    )

                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        listOf(
                            "Маршрут",
                            "Диспетчер",
                            "SOS"
                        ).forEach {
                            OutlinedButton(
                                onClick = {},
                                enabled = !loading
                            ) {
                                Text(it, color = fg)
                            }
                        }
                    }
                }

                if (loading) {
                    item {
                        LinearProgressIndicator(
                            modifier = Modifier.fillMaxWidth(),
                            color = Teal
                        )
                    }
                }

                if (errorMessage.isNotBlank()) {
                    item {
                        Text(
                            errorMessage,
                            color = MaterialTheme.colorScheme.error,
                            fontSize = 12.sp
                        )
                    }
                }

                if (infoMessage.isNotBlank()) {
                    item {
                        Text(
                            infoMessage,
                            color = Teal,
                            fontSize = 12.sp
                        )
                    }
                }
            }
        }
    }
}
