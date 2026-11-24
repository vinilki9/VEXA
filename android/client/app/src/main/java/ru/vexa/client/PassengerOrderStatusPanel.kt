
package ru.vexa.client

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject


@Composable
fun PassengerOrderStatusPanel(
    orderIdentifier: String,
    modifier: Modifier = Modifier,
    onTerminal: () -> Unit = {},
    onNewTrip: () -> Unit = {}
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
    var authenticationError by remember(orderIdentifier) {
        mutableStateOf(false)
    }
    var confirmCancellation by remember(orderIdentifier) { mutableStateOf(false) }
    var cancelling by remember(orderIdentifier) { mutableStateOf(false) }
    var cancellationError by remember(orderIdentifier) { mutableStateOf<String?>(null) }
    val coroutineScope = rememberCoroutineScope()

    LaunchedEffect(orderIdentifier) {
        while (true) {
            try {
                val response = ApiClient.getPassengerOrder(orderIdentifier)
                val current = JSONObject(response)
                order = current
                connectionError = false
                authenticationError = false
                loading = false

                if (current.optString("status") in setOf("completed", "cancelled", "no_driver_found")) {
                    break
                }
            } catch (error: ApiHttpException) {
                connectionError = true
                loading = false
                if (error.statusCode == 401 || error.statusCode == 403) {
                    authenticationError = true
                    break // Повторный запрос без новой авторизации бесполезен.
                }
            } catch (_: Exception) {
                connectionError = true
                loading = false
            }

            delay(5000)
        }
    }

    if (confirmCancellation) {
        AlertDialog(
            onDismissRequest = { if (!cancelling) confirmCancellation = false },
            title = { Text("Отменить заказ?") },
            text = { Text("Заказ ещё не назначен водителю. Отмену нельзя будет отменить.") },
            confirmButton = {
                TextButton(
                    enabled = !cancelling,
                    onClick = {
                        cancelling = true
                        cancellationError = null
                        coroutineScope.launch {
                            try {
                                val response = ApiClient.cancelPassengerOrder(orderIdentifier)
                                order = JSONObject(response)
                                connectionError = false
                                confirmCancellation = false
                            } catch (error: ApiHttpException) {
                                cancellationError = when (error.statusCode) {
                                    409 -> "Статус заказа изменился. Обновите данные или свяжитесь с диспетчером."
                                    401, 403 -> "Войдите в профиль заново, чтобы отменить заказ."
                                    else -> "Не удалось отменить заказ. Проверьте соединение."
                                }
                                confirmCancellation = false
                            } catch (_: Exception) {
                                cancellationError = "Не удалось отменить заказ. Повторите попытку."
                                confirmCancellation = false
                            } finally {
                                cancelling = false
                            }
                        }
                    }
                ) { Text(if (cancelling) "Отменяем..." else "Отменить заказ") }
            },
            dismissButton = {
                TextButton(onClick = { confirmCancellation = false }, enabled = !cancelling) {
                    Text("Назад")
                }
            }
        )
    }

    val currentOrder = order
    val status = currentOrder?.optString("status").orEmpty()

    LaunchedEffect(status) {
        if (status == "completed" || status == "cancelled" || status == "no_driver_found") onTerminal()
    }

    val statusLabel = when (status) {
        "new" -> "Заказ отправлен"
        "accepted" -> "Поиск водителя"
        "assigned" -> "Водитель назначен"
        "arrived" -> "Водитель на месте"
        "in_progress" -> "Поездка выполняется"
        "completed" -> "Поездка завершена"
        "cancelled" -> "Заказ отменён"
        "no_driver_found" -> "Свободных машин не найдено"
        else -> "Ожидаем обновления заказа"
    }

    val statusDescription = when (status) {
        "new" -> "Ищем возможность принять ваш заказ."
        "accepted" -> "VEXA автоматически подбирает вам водителя."
        "assigned" -> "Водитель назначен и направляется к вам."
        "arrived" -> "Водитель прибыл по адресу подачи."
        "in_progress" -> "Вы в пути. Хорошей поездки!"
        "completed" -> "Спасибо, что воспользовались VEXA."
        "cancelled" -> "Этот заказ больше не выполняется."
        "no_driver_found" -> "Свободных машин поблизости нет. Можно попробовать оформить новый заказ позже."
        else -> "Состояние поездки обновляется с сервера."
    }

    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "Состояние поездки",
                color = MaterialTheme.colorScheme.onSurface,
                style = MaterialTheme.typography.titleMedium
            )

            Text(
                text = statusLabel,
                color = when (status) {
                    "cancelled", "no_driver_found" -> MaterialTheme.colorScheme.error
                    "completed" -> MaterialTheme.colorScheme.primary
                    else -> MaterialTheme.colorScheme.primary
                },
                style = MaterialTheme.typography.titleLarge
            )

            Text(
                text = statusDescription,
                color = MaterialTheme.colorScheme.onSurface,
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
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.bodySmall
                    )
                }

                if (pickup.isNotBlank()) {
                    Text(
                        text = "Откуда: $pickup",
                        color = MaterialTheme.colorScheme.onSurface,
                        style = MaterialTheme.typography.bodySmall
                    )
                }

                if (destination.isNotBlank()) {
                    Text(
                        text = "Куда: $destination",
                        color = MaterialTheme.colorScheme.onSurface,
                        style = MaterialTheme.typography.bodySmall
                    )
                }

                if (price != null && price != JSONObject.NULL) {
                    Text(
                        text = "Стоимость: $price ₽",
                        color = MaterialTheme.colorScheme.onSurface,
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }

            if (status == "new" || status == "accepted") {
                OutlinedButton(
                    onClick = { confirmCancellation = true },
                    enabled = !cancelling && !authenticationError,
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Отменить заказ") }
            }
            cancellationError?.let { error ->
                Text(text = error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }

            if (status == "completed" || status == "cancelled" || status == "no_driver_found") {
                OutlinedButton(onClick = onNewTrip, modifier = Modifier.fillMaxWidth()) {
                    Text("Новая поездка")
                }
            }

            if (loading) {
                Text(
                    text = "Получаем состояние заказа...",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodySmall
                )
            } else if (authenticationError) {
                Text(
                    text = "Сеанс истёк или доступ к заказу запрещён. Войдите в профиль заново.",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall
                )
            } else if (connectionError) {
                Text(
                    text = "Не удалось обновить данные. Повторяем запрос...",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall
                )
            } else if (
                status != "completed" &&
                status != "cancelled" &&
                status != "no_driver_found"
            ) {
                Text(
                    text = "Автоматическое обновление каждые 5 секунд",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }
    }
}
