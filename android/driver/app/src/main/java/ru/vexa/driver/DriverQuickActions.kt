package ru.vexa.driver

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import org.json.JSONObject

/** Quick actions only: VEXA MAP in-app offline turn-by-turn navigation is a separate feature. */
object DriverQuickActions {
    fun validPoint(point: JSONObject?): Boolean {
        val lat = point?.optDouble("latitude", Double.NaN) ?: Double.NaN
        val lon = point?.optDouble("longitude", Double.NaN) ?: Double.NaN
        return lat.isFinite() && lon.isFinite() && lat in -90.0..90.0 && lon in -180.0..180.0
    }

    fun openNavigator(context: Context, point: JSONObject?) {
        if (!validPoint(point)) {
            Toast.makeText(context, "Нет координат адреса", Toast.LENGTH_SHORT).show()
            return
        }
        val lat = point!!.getDouble("latitude")
        val lon = point.getDouble("longitude")
        // Geo URI delegates routing to the installed navigation application.
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse("geo:$lat,$lon?q=$lat,$lon"))
        try {
            context.startActivity(Intent.createChooser(intent, "Открыть навигатор"))
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(context, "Установленный навигатор не найден", Toast.LENGTH_LONG).show()
        } catch (_: SecurityException) {
            Toast.makeText(context, "Не удалось открыть навигатор", Toast.LENGTH_LONG).show()
        }
    }

    fun validPhone(phone: String): Boolean {
        val normalized = phone.filter { it.isDigit() || it == '+' }
        return normalized.count { it.isDigit() } in 7..15 &&
            normalized.count { it == '+' } <= 1 &&
            (!normalized.contains('+') || normalized.startsWith('+'))
    }

    fun openDialer(context: Context, phone: String) {
        if (!validPhone(phone)) {
            Toast.makeText(context, "Номер пассажира недоступен", Toast.LENGTH_SHORT).show()
            return
        }
        val clean = phone.filter { it.isDigit() || it == '+' }
        try {
            context.startActivity(Intent(Intent.ACTION_DIAL, Uri.fromParts("tel", clean, null)))
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(context, "Приложение телефона не найдено", Toast.LENGTH_LONG).show()
        } catch (_: SecurityException) {
            Toast.makeText(context, "Не удалось открыть телефон", Toast.LENGTH_LONG).show()
        }
    }
}
