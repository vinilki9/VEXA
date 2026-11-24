package ru.vexa.driver

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import org.json.JSONObject

/** Оповещение о НОВОМ предложении. Вызывается фоновым DriverLocationService. */
internal object DriverOfferAlerts {
    private const val CHANNEL = "vexa_driver_new_offer_v1"
    private const val NOTIFICATION_ID = 2402
    private const val ALERT_STATE = "vexa_driver_offer_alerts_state"
    private const val LAST_ID = "last_alerted_offer_id"

    fun onPoll(context: Context, response: JSONObject) {
        val offers = response.optJSONArray("offers")
        if (offers == null || offers.length() == 0) {
            clearNotification(context)
            return
        }
        val ids = buildList {
            for (i in 0 until offers.length()) {
                offers.optJSONObject(i)?.optString("offer_id")?.let { add(it) }
            }
        }
        val prefs = context.getSharedPreferences(ALERT_STATE, Context.MODE_PRIVATE)
        val newId = DriverOfferAlertPolicy.newOfferId(prefs.getString(LAST_ID, null), ids) ?: return
        // commit() не даёт повторно озвучить то же предложение при быстром рестарте сервиса.
        if (!prefs.edit().putString(LAST_ID, newId).commit()) return
        val settings = DriverPreferences.load(context)
        if (settings.alertsEnabled) {
            showNotification(context)
            playAlert(context, settings)
        }
    }

    fun preview(context: Context, settings: DriverPreferences.State) {
        playAlert(context, settings)
    }

    fun clearNotification(context: Context) {
        (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .cancel(NOTIFICATION_ID)
    }

    private fun showNotification(context: Context) {
        if (Build.VERSION.SDK_INT >= 33 &&
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            // Канал намеренно без встроенного сигнала: звук и вибрация управляются настройками VEXA.
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL, "Новые заказы VEXA", NotificationManager.IMPORTANCE_HIGH)
                    .apply {
                        description = "Предложения новых заказов водителю"
                        setSound(null, null)
                        enableVibration(false)
                    }
            )
        }
        val openApp = PendingIntent.getActivity(
            context, 1, Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = Notification.Builder(context, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("VEXA Driver · новый заказ")
            .setContentText("Откройте приложение, чтобы принять предложение")
            .setContentIntent(openApp)
            .setAutoCancel(true)
            .setVisibility(Notification.VISIBILITY_PRIVATE)
            .setCategory(Notification.CATEGORY_MESSAGE)
            .build()
        try {
            manager.notify(NOTIFICATION_ID, notification)
        } catch (_: SecurityException) {
            // Разрешение на системные уведомления может быть отозвано в любой момент.
        }
    }

    private fun playAlert(context: Context, settings: DriverPreferences.State) {
        if (!settings.alertsEnabled) return
        if (settings.volume > 0) {
            // Никаких внешних аудиофайлов: используются системные тоны Android.
            val tone = when (settings.soundProfile) {
                "modern" -> ToneGenerator.TONE_PROP_ACK
                "soft" -> ToneGenerator.TONE_PROP_PROMPT
                "dynamic" -> ToneGenerator.TONE_PROP_BEEP2
                "calm" -> ToneGenerator.TONE_SUP_PIP
                "premium" -> ToneGenerator.TONE_SUP_RADIO_ACK
                else -> ToneGenerator.TONE_PROP_BEEP
            }
            try {
                val generator = ToneGenerator(AudioManager.STREAM_NOTIFICATION, settings.volume)
                generator.startTone(tone, 300)
                Handler(Looper.getMainLooper()).postDelayed({ generator.release() }, 450)
            } catch (_: RuntimeException) {
                // Без звукового устройства приложение не должно падать.
            }
        }
        if (settings.vibrationEnabled) {
            try {
                val vibrator = if (Build.VERSION.SDK_INT >= 31) {
                    context.getSystemService(VibratorManager::class.java).defaultVibrator
                } else {
                    @Suppress("DEPRECATION")
                    (context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator)
                }
                if (vibrator.hasVibrator()) {
                    vibrator.vibrate(VibrationEffect.createOneShot(230, VibrationEffect.DEFAULT_AMPLITUDE))
                }
            } catch (_: SecurityException) {
                // Не мешаем при отзыве разрешений или отсутствии вибромотора.
            }
        }
    }
}
