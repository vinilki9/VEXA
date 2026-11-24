package ru.vexa.client

import android.content.Context
import android.content.Intent

/** Explicit share action; no fake live-tracking link or authorization token. */
internal object VexaRideShare {
    fun share(context: Context, orderNumber: String, pickup: String, destination: String) {
        require(orderNumber.isNotBlank()) { "Номер заказа отсутствует" }
        val message = buildString {
            append("Моя поездка VEXA № ").append(orderNumber.trim()).append('\n')
            append("Откуда: ").append(pickup.trim()).append('\n')
            append("Куда: ").append(destination.trim()).append('\n')
            append("Это сведения о заказе, не ссылка для отслеживания в реальном времени.")
        }
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, message)
        }
        context.startActivity(Intent.createChooser(intent, "Поделиться сведениями о поездке"))
    }
}
