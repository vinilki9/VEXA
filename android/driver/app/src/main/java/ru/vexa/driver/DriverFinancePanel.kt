
package ru.vexa.driver

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import kotlinx.coroutines.launch

private val FinanceTeal = Color(0xFF20C6B7)
private val FinanceMuted = Color(0xFF64748B)

private fun formatFinanceMoney(kopecks: Long): String {
    val rubles = kopecks / 100
    val remainder = kotlin.math.abs(kopecks % 100)

    return "%,d.%02d ₽".format(
        java.util.Locale("ru", "RU"),
        rubles,
        remainder
    )
}

private fun paymentMethodLabel(method: String): String {
    return when (method) {
        "cash" -> "Наличные"
        "driver_transfer" -> "Перевод водителю"
        "card" -> "Банковская карта"
        "sbp" -> "СБП"
        else -> method
    }
}

private fun walletTransactionLabel(type: String): String {
    return when (type) {
        "commission_debit" -> "Комиссия VEXA"
        "electronic_earning_credit" -> "Зачисление за поездку"
        "payout_reserve" -> "Резервирование выплаты"
        "payout_release" -> "Возврат резерва выплаты"
        "payout_completed" -> "Выплата"
        "manual_adjustment" -> "Корректировка баланса"
        else -> "Операция по кошельку"
    }
}

private fun formatWalletDate(value: String): String {
    if (value.isBlank()) return "Дата не указана"
    return value.replace("T", " ")
        .removeSuffix("Z")
        .take(16)
}

@Composable
fun DriverFinancePanel(
    dark: Boolean,
    foregroundColor: Color,
    secondaryText: Color
) {
    var summary by remember {
        mutableStateOf<JSONObject?>(null)
    }

    var transactions by remember {
        mutableStateOf(listOf<JSONObject>())
    }

    var selectedOrder by remember {
        mutableStateOf<JSONObject?>(null)
    }

    var orderLoading by remember {
        mutableStateOf(false)
    }

    var orderError by remember {
        mutableStateOf("")
    }

    val coroutineScope = rememberCoroutineScope()

    var loading by remember {
        mutableStateOf(false)
    }

    var errorMessage by remember {
        mutableStateOf("")
    }

    var refreshKey by remember {
        mutableStateOf(0)
    }

    LaunchedEffect(refreshKey) {
        loading = true
        errorMessage = ""

        val result = withContext(Dispatchers.IO) {
            try {
                val loadedSummary =
                    DriverApiClient.getFinanceSummary()

                val history =
                    DriverApiClient.getWalletTransactions(
                        limit = 50,
                        offset = 0
                    )

                val array = history.optJSONArray("items")
                val loadedTransactions =
                    mutableListOf<JSONObject>()

                if (array != null) {
                    for (index in 0 until array.length()) {
                        loadedTransactions.add(
                            array.getJSONObject(index)
                        )
                    }
                }

                Triple(
                    loadedSummary,
                    loadedTransactions,
                    null as String?
                )
            } catch (exception: Exception) {
                Triple(
                    null,
                    emptyList<JSONObject>(),
                    exception.message
                        ?: "Не удалось загрузить финансы"
                )
            }
        }

        summary = result.first
        transactions = result.second
        errorMessage = result.third.orEmpty()
        loading = false
    }

    val cardColor = if (dark) {
        Color(0xFF1E293B)
    } else {
        Color.White
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(
            containerColor = cardColor
        ),
        elevation = CardDefaults.cardElevation(
            defaultElevation = if (dark) 0.dp else 2.dp
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(
                    modifier = Modifier.weight(1f)
                ) {
                    Text(
                        text = "Мои финансы",
                        color = foregroundColor,
                        fontSize = 19.sp,
                        fontWeight = FontWeight.Bold
                    )

                    Text(
                        text = "Заработок и комиссия сервиса",
                        color = secondaryText,
                        fontSize = 11.sp
                    )
                }

                Button(
                    onClick = {
                        if (!loading) {
                            refreshKey++
                        }
                    },
                    enabled = !loading,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = FinanceTeal,
                        contentColor = Color(0xFF111827)
                    ),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(
                        text = "Обновить",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            if (loading && summary == null) {
                CircularProgressIndicator(
                    modifier = Modifier.align(Alignment.CenterHorizontally),
                    color = FinanceTeal
                )
            }

            if (errorMessage.isNotBlank()) {
                Text(
                    text = errorMessage,
                    color = MaterialTheme.colorScheme.error,
                    fontSize = 12.sp
                )
            }

            val data = summary

            if (data != null) {
                val fare = data.optLong("fare_total_kopecks")
                val commission =
                    data.optLong("commission_total_kopecks")
                val earnings =
                    data.optLong("earnings_total_kopecks")
                val debt =
                    data.optLong("cash_debt_kopecks")

                val trips = data.optInt("completed_trips")
                val rating = data.optString("current_rating", "—")
                val commissionRate =
                    data.optString(
                        "current_commission_rate_percent",
                        "—"
                    )

                HorizontalDivider(
                    color = secondaryText.copy(alpha = 0.2f)
                )

                FinanceMetric(
                    title = "Ваш заработок",
                    value = formatFinanceMoney(earnings),
                    valueColor = FinanceTeal,
                    foregroundColor = foregroundColor,
                    secondaryText = secondaryText,
                    large = true
                )

                FinanceMetric(
                    title = "Общая стоимость поездок",
                    value = formatFinanceMoney(fare),
                    foregroundColor = foregroundColor,
                    secondaryText = secondaryText
                )

                FinanceMetric(
                    title = "Комиссия сервиса",
                    value = formatFinanceMoney(commission),
                    foregroundColor = foregroundColor,
                    secondaryText = secondaryText
                )

                FinanceMetric(
                    title = "Задолженность за наличные и переводы",
                    value = formatFinanceMoney(debt),
                    valueColor = if (debt > 0) {
                        Color(0xFFE59A36)
                    } else {
                        FinanceTeal
                    },
                    foregroundColor = foregroundColor,
                    secondaryText = secondaryText
                )

                HorizontalDivider(
                    color = secondaryText.copy(alpha = 0.2f)
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    FinanceInfo(
                        title = "Рейтинг",
                        value = rating,
                        foregroundColor = foregroundColor,
                        secondaryText = secondaryText
                    )

                    FinanceInfo(
                        title = "Комиссия сейчас",
                        value = "$commissionRate%",
                        foregroundColor = foregroundColor,
                        secondaryText = secondaryText
                    )

                    FinanceInfo(
                        title = "Поездки",
                        value = trips.toString(),
                        foregroundColor = foregroundColor,
                        secondaryText = secondaryText
                    )
                }
            }

            HorizontalDivider(
                color = secondaryText.copy(alpha = 0.2f)
            )

            Text(
                text = "История кошелька",
                color = foregroundColor,
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold
            )

            if (transactions.isEmpty() && !loading) {
                Text(
                    text = "Операций по кошельку пока нет",
                    color = secondaryText,
                    fontSize = 12.sp
                )
            }

            transactions.forEach { transaction ->
                val transactionType = transaction.optString("transaction_type", "")
                val orderId = transaction.optString("order_id", "")
                val orderNumber = transaction.optString("order_public_number", "")
                val change = transaction.optLong("balance_change_kopecks")
                val balanceAfter = transaction.optLong("balance_after_kopecks")
                val paymentMethod = transaction.optString("payment_method", "")
                val date = formatWalletDate(transaction.optString("created_at", ""))

                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Text(
                        text = walletTransactionLabel(transactionType),
                        color = foregroundColor,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold
                    )

                    Text(
                        text = buildString {
                            append(date)
                            if (paymentMethod.isNotBlank()) {
                                append(" · ")
                                append(paymentMethodLabel(paymentMethod))
                            }
                        },
                        color = secondaryText,
                        fontSize = 10.sp
                    )

                    if (orderNumber.isNotBlank() && orderId.isNotBlank()) {
                        Text(
                            text = "Заказ №$orderNumber",
                            modifier = Modifier.clickable {
                                if (!orderLoading) {
                                    orderLoading = true
                                    orderError = ""
                                    selectedOrder = null
                                    coroutineScope.launch {
                                        try {
                                            selectedOrder = withContext(Dispatchers.IO) {
                                                DriverApiClient.getOrder(orderId)
                                            }
                                        } catch (exception: Exception) {
                                            orderError = exception.message
                                                ?: "Не удалось загрузить заказ"
                                        } finally {
                                            orderLoading = false
                                        }
                                    }
                                }
                            },
                            color = FinanceTeal,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }

                    FinanceMetric(
                        title = if (change >= 0) "Зачислено" else "Списано",
                        value = formatFinanceMoney(kotlin.math.abs(change)),
                        valueColor = if (change >= 0) FinanceTeal else Color(0xFFE59A36),
                        foregroundColor = foregroundColor,
                        secondaryText = secondaryText,
                        large = true
                    )

                    FinanceMetric(
                        title = "Баланс после операции",
                        value = formatFinanceMoney(balanceAfter),
                        foregroundColor = foregroundColor,
                        secondaryText = secondaryText
                    )
                }

                HorizontalDivider(
                    color = secondaryText.copy(alpha = 0.15f)
                )
            }

            Text(
                text = "Показаны последние 50 операций. Причины изменения баланса не отображаются.",
                color = secondaryText,
                fontSize = 10.sp
            )

            if (orderLoading || orderError.isNotBlank() || selectedOrder != null) {
                AlertDialog(
                    onDismissRequest = {
                        if (!orderLoading) {
                            selectedOrder = null
                            orderError = ""
                        }
                    },
                    title = {
                        Text("Карточка поездки", fontWeight = FontWeight.Bold)
                    },
                    text = {
                        when {
                            orderLoading -> CircularProgressIndicator(color = FinanceTeal)
                            orderError.isNotBlank() -> Text(
                                text = orderError,
                                color = MaterialTheme.colorScheme.error
                            )
                            selectedOrder != null -> {
                                val order = selectedOrder!!
                                val pickup = order.optJSONObject("pickup")
                                    ?.optString("address").orEmpty()
                                val destination = order.optJSONObject("destination")
                                    ?.optString("address").orEmpty()
                                val vehicle = order.optJSONObject("vehicle")
                                val vehicleText = if (vehicle != null) {
                                    listOf(
                                        vehicle.optString("make"),
                                        vehicle.optString("model"),
                                        vehicle.optString("color")
                                    ).filter { it.isNotBlank() }.joinToString(" ")
                                } else ""

                                Column(
                                    verticalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    Text(
                                        text = "Заказ №${order.optString("public_number", "—")}",
                                        color = foregroundColor,
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 14.sp
                                    )
                                    Text(
                                        text = "Статус: ${order.optString("status", "—")}",
                                        color = foregroundColor,
                                        fontSize = 12.sp
                                    )
                                    if (pickup.isNotBlank()) {
                                        Text("Откуда: $pickup", color = foregroundColor, fontSize = 12.sp)
                                    }
                                    if (destination.isNotBlank()) {
                                        Text("Куда: $destination", color = foregroundColor, fontSize = 12.sp)
                                    }
                                    Text(
                                        text = "Стоимость: ${formatFinanceMoney(order.optLong("price_kopecks"))}",
                                        color = foregroundColor,
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                    if (vehicleText.isNotBlank()) {
                                        Text("Автомобиль: $vehicleText", color = foregroundColor, fontSize = 12.sp)
                                    }
                                    vehicle?.optString("license_plate")
                                        ?.takeIf { it.isNotBlank() }
                                        ?.let { plate ->
                                            Text(
                                                text = "Госномер: $plate",
                                                color = foregroundColor,
                                                fontSize = 12.sp,
                                                fontWeight = FontWeight.Bold
                                            )
                                        }
                                }
                            }
                        }
                    },
                    confirmButton = {
                        TextButton(
                            onClick = {
                                selectedOrder = null
                                orderError = ""
                            },
                            enabled = !orderLoading
                        ) {
                            Text("Закрыть")
                        }
                    }
                )
            }
        }
    }
}

@Composable
private fun FinanceMetric(
    title: String,
    value: String,
    foregroundColor: Color,
    secondaryText: Color,
    valueColor: Color = foregroundColor,
    large: Boolean = false
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = title,
            modifier = Modifier.weight(1f),
            color = secondaryText,
            fontSize = if (large) 12.sp else 11.sp
        )

        Text(
            text = value,
            color = valueColor,
            fontSize = if (large) 20.sp else 12.sp,
            fontWeight = FontWeight.Bold
        )
    }
}

@Composable
private fun FinanceInfo(
    title: String,
    value: String,
    foregroundColor: Color,
    secondaryText: Color
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(3.dp)
    ) {
        Text(
            text = title,
            color = secondaryText,
            fontSize = 10.sp
        )

        Text(
            text = value,
            color = foregroundColor,
            fontSize = 14.sp,
            fontWeight = FontWeight.Bold
        )
    }
}
