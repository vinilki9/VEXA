
package ru.vexa.driver

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
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
                    DriverApiClient.getFinanceTransactions(
                        limit = 20,
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
                    title = "Задолженность за наличные заказы",
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
                text = "История операций",
                color = foregroundColor,
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold
            )

            if (transactions.isEmpty() && !loading) {
                Text(
                    text = "Финансовых операций пока нет",
                    color = secondaryText,
                    fontSize = 12.sp
                )
            }

            transactions.forEach { transaction ->
                val description = transaction.optString(
                    "description",
                    "Финансовая операция"
                )

                val payment = paymentMethodLabel(
                    transaction.optString("payment_method", "")
                )

                val fareAmount = transaction.optLong(
                    "fare_kopecks"
                )

                val commissionAmount = transaction.optLong(
                    "commission_kopecks"
                )

                val earningAmount = transaction.optLong(
                    "driver_earning_kopecks"
                )

                val debtChange = transaction.optLong(
                    "debt_change_kopecks"
                )

                val rate = transaction.optString(
                    "commission_rate_percent",
                    "—"
                )

                val date = transaction.optString(
                    "created_at",
                    ""
                ).replace("T", " ").take(16)

                Column(
                    verticalArrangement = Arrangement.spacedBy(5.dp)
                ) {
                    Text(
                        text = description,
                        color = foregroundColor,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )

                    Text(
                        text = "$date · $payment",
                        color = secondaryText,
                        fontSize = 10.sp
                    )

                    FinanceMetric(
                        title = "Стоимость",
                        value = formatFinanceMoney(fareAmount),
                        foregroundColor = foregroundColor,
                        secondaryText = secondaryText
                    )

                    FinanceMetric(
                        title = "Комиссия $rate%",
                        value = formatFinanceMoney(commissionAmount),
                        foregroundColor = foregroundColor,
                        secondaryText = secondaryText
                    )

                    FinanceMetric(
                        title = "Вам начислено",
                        value = formatFinanceMoney(earningAmount),
                        valueColor = FinanceTeal,
                        foregroundColor = foregroundColor,
                        secondaryText = secondaryText
                    )

                    if (debtChange > 0) {
                        FinanceMetric(
                            title = "Увеличение долга",
                            value = formatFinanceMoney(debtChange),
                            valueColor = Color(0xFFE59A36),
                            foregroundColor = foregroundColor,
                            secondaryText = secondaryText
                        )
                    }
                }

                HorizontalDivider(
                    color = secondaryText.copy(alpha = 0.15f)
                )
            }

            Text(
                text = "Данные загружаются с сервера VEXA. " +
                    "История показывает последние 20 операций.",
                color = secondaryText,
                fontSize = 10.sp
            )
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
