
package ru.vexa.client

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import org.json.JSONArray
import org.json.JSONObject

private val StatusTeal = Color(0xFF1ED9C6)
private val StatusInk = Color(0xFF111827)
private val StatusGray = Color(0xFF6B7280)
private val StatusRed = Color(0xFFE53935)

@Composable
fun PassengerOrderStatusPanel(
    orderIdentifier: String,
    modifier: Modifier = Modifier
) {
    var order by remember(orderIdentifier) {
        mutableStateOf<JSONObject?>(null)
    }

    var loading by remember(orderIdentifier) {
        mutableStateOf(true)
    }

    var connectionError by remember(orderIdentifier) {
        mutableStateOf(false)
    }

    LaunchedEffect(orderIdentifier) {
        while (true) {
            try {
                val response = ApiClient.getPassengerOrders()
                val orders = JSONArray(response)

                var foundOrder: JSONObject? = null

                for (index in 0 until orders.length()) {
                    val item = orders.optJSONObject(index)
                        ?: continue

                    val id = item.optString("id")
                    val publicNumber = item.optString("public_number")

                    if (
                        id == orderIdentifier ||
                        publicNumber == orderIdentifier
                    ) {
                        foundOrder = item
                        break
                    }
                }

                if (foundOrder != null) {
                    order = foundOrder
                    connectionError = false
                    loading = false

                    val status = foundOrder.optString("status")

                    if (
                        status == "completed" ||
                        status == "cancelled"
                    ) {
                        break
                    }
                } else {
                    connectionError = true
                    loading = false
                }
            } catch (_: Exception) {
                connectionError = true
                loading = false
            }

            delay(5000)
        }
    }

    val currentOrder = order
    val status = currentOrder?.optString("status").orEmpty()

    val statusLabel = when (status) {
        "new" -> "Заказ отправлен"
        "accepted" -> "Заказ принят диспетчером"
        "assigned" -> "Водитель назначен"
        "arrived" -> "Водитель на месте"
        "in_progress" -> "Поездка выполняется"
        "completed" -> "Поездка завершена"
        "cancelled" -> "Заказ отменён"
        else -> "Ожидаем обновления заказа"
    }

    val statusDescription = when (status) {
        "new" -> "Ищем возможность принять ваш заказ."
        "accepted" -> "Диспетчер принял заказ. Подбираем водителя."
        "assigned" -> "Водитель назначен и направляется к вам."
        "arrived" -> "Водитель прибыл по адресу подачи."
        "in_progress" -> "Вы в пути. Хорошей поездки!"
        "completed" -> "Спасибо, что воспользовались VEXA."
        "cancelled" -> "Этот заказ больше не выполняется."
        else -> "Состояние поездки обновляется с сервера."
    }

    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = Color(0xFFF7FAFA)
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "Состояние поездки",
                color = StatusInk,
                style = MaterialTheme.typography.titleMedium
            )

            Text(
                text = statusLabel,
                color = when (status) {
                    "cancelled" -> StatusRed
                    "completed" -> StatusTeal
                    else -> StatusTeal
                },
                style = MaterialTheme.typography.titleLarge
            )

            Text(
                text = statusDescription,
                color = StatusInk,
                style = MaterialTheme.typography.bodyMedium
            )

            currentOrder?.let { item ->
                val pickup = item.optString("pickup_address")
                val destination = item.optString("destination_address")
                val number = item.optString("public_number")
                val price = item.opt("price_rub")

                if (number.isNotBlank()) {
                    Text(
                        text = "Заказ №$number",
                        color = StatusGray,
                        style = MaterialTheme.typography.bodySmall
                    )
                }

                if (pickup.isNotBlank()) {
                    Text(
                        text = "Откуда: $pickup",
                        color = StatusInk,
                        style = MaterialTheme.typography.bodySmall
                    )
                }

                if (destination.isNotBlank()) {
                    Text(
                        text = "Куда: $destination",
                        color = StatusInk,
                        style = MaterialTheme.typography.bodySmall
                    )
                }

                if (price != null && price != JSONObject.NULL) {
                    Text(
                        text = "Стоимость: $price ₽",
                        color = StatusInk,
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }

            if (loading) {
                Text(
                    text = "Получаем состояние заказа...",
                    color = StatusGray,
                    style = MaterialTheme.typography.bodySmall
                )
            } else if (connectionError) {
                Text(
                    text = "Не удалось обновить данные. Повторяем запрос...",
                    color = StatusRed,
                    style = MaterialTheme.typography.bodySmall
                )
            } else if (
                status != "completed" &&
                status != "cancelled"
            ) {
                Text(
                    text = "Автоматическое обновление каждые 5 секунд",
                    color = StatusGray,
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }
    }
}
