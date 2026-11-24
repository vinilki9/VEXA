package ru.vexa.client

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import org.json.JSONArray
import org.json.JSONObject

private fun statusLabel(status: String): String = when (status) {
    "new" -> "Создан"
    "accepted" -> "Принят"
    "assigned" -> "Водитель назначен"
    "arrived" -> "Водитель прибыл"
    "in_progress" -> "В пути"
    "completed" -> "Завершён"
    "cancelled" -> "Отменён"
    "no_driver_found" -> "Машина не найдена"
    else -> "Статус уточняется"
}

/** Never fabricate a location when a historical order has no valid coordinates. */
private fun historicalPoint(order: JSONObject, prefix: String): AddressResult? {
    val name = order.optString("${prefix}_address").trim()
    val lat = order.optDouble("${prefix}_latitude", Double.NaN)
    val lon = order.optDouble("${prefix}_longitude", Double.NaN)
    return if (name.isNotEmpty() && lat.isFinite() && lon.isFinite() &&
        lat in -90.0..90.0 && lon in -180.0..180.0
    ) AddressResult(name, lat, lon) else null
}

/** Server-backed history, scoped by the Backend to the authenticated passenger. */
@Composable
fun VexaTripHistoryDialog(
    onDismiss: () -> Unit,
    onRepeatTrip: (AddressResult, AddressResult) -> Unit
) {
    var refreshKey by remember { mutableIntStateOf(0) }
    var loading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var orders by remember { mutableStateOf<List<JSONObject>>(emptyList()) }

    LaunchedEffect(refreshKey) {
        loading = true
        errorMessage = null
        orders = emptyList() // Do not show data left over from a different login.
        try {
            if (ApiClient.getAccessToken().isNullOrBlank()) {
                throw IllegalStateException("Войдите в профиль, чтобы посмотреть поездки.")
            }
            val list = JSONArray(ApiClient.getPassengerOrders())
            orders = buildList {
                for (index in 0 until list.length()) {
                    list.optJSONObject(index)?.let { add(it) }
                }
            }
        } catch (error: Exception) {
            if (error is kotlinx.coroutines.CancellationException) throw error
            errorMessage = if (error is ApiHttpException &&
                (error.statusCode == 401 || error.statusCode == 403)
            ) "Сессия завершилась. Войдите в профиль повторно."
            else error.message ?: "Не удалось загрузить историю поездок."
        } finally {
            loading = false
        }
    }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Surface(
            modifier = Modifier.fillMaxWidth(0.95f).fillMaxHeight(0.85f),
            shape = MaterialTheme.shapes.large,
            color = MaterialTheme.colorScheme.surface
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Row(modifier = Modifier.fillMaxWidth()) {
                    Text(
                        "Мои поездки",
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.titleLarge
                    )
                    TextButton(onClick = { refreshKey++ }, enabled = !loading) {
                        Text("Обновить")
                    }
                }
                Text("Последние 50 заказов из VEXA Backend",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                HorizontalDivider()
                if (loading) {
                    CircularProgressIndicator()
                    Text("Загружаем заказы…")
                }
                errorMessage?.let {
                    Text(it, color = MaterialTheme.colorScheme.error)
                }
                if (!loading && errorMessage == null && orders.isEmpty()) {
                    Text("Пока нет поездок. После первого заказа они появятся здесь.")
                }
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(orders, key = { it.optString("id") }) { order ->
                        val pickup = historicalPoint(order, "pickup")
                        val destination = historicalPoint(order, "destination")
                        val number = order.optString("public_number").ifBlank { "—" }
                        val price = order.optString("price_rub").takeIf { it.isNotBlank() && it != "null" }
                        val date = order.optString("created_at").take(10)
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(
                                modifier = Modifier.padding(12.dp),
                                verticalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                Text("№ $number • ${statusLabel(order.optString("status"))}",
                                    style = MaterialTheme.typography.titleSmall)
                                if (date.isNotBlank()) Text(date, style = MaterialTheme.typography.bodySmall)
                                Text("Откуда: ${order.optString("pickup_address")}")
                                Text("Куда: ${order.optString("destination_address")}")
                                price?.let { Text("Стоимость: $it ₽") }
                                OutlinedButton(
                                    onClick = { if (pickup != null && destination != null) onRepeatTrip(pickup, destination) },
                                    enabled = pickup != null && destination != null
                                ) { Text("Повторить маршрут") }
                            }
                        }
                    }
                }
                Text("Повтор маршрута только заполнит адреса. Стоимость будет рассчитана заново.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodySmall)
                Button(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) {
                    Text("К карте")
                }
            }
        }
    }
}
