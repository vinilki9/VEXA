
package ru.vexa.driver

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import java.util.concurrent.Executors

class DriverLocationService : Service() {

    companion object {
        private const val TAG = "VEXA_GPS"
        private const val ACTION_START = "ru.vexa.driver.GPS_START"
        private const val ACTION_STOP = "ru.vexa.driver.GPS_STOP"

        private const val CHANNEL_ID = "vexa_driver_location"
        private const val NOTIFICATION_ID = 2401

        private const val IDLE_INTERVAL_MS = 30_000L
        private const val TRIP_INTERVAL_MS = 5_000L
        private const val ORDER_REFRESH_INTERVAL_MS = 10_000L

        fun start(context: Context) {
            val intent = Intent(context, DriverLocationService::class.java)
                .setAction(ACTION_START)

            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(intent)
                } else {
                    context.startService(intent)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Не удалось запустить GPS-сервис", e)
            }
        }

        fun stop(context: Context) {
            val intent = Intent(context, DriverLocationService::class.java)
                .setAction(ACTION_STOP)

            try {
                context.startService(intent)
            } catch (e: Exception) {
                Log.e(TAG, "Не удалось остановить GPS-сервис", e)
            }
        }
    }

    private val handler = Handler(Looper.getMainLooper())
    private val networkExecutor = Executors.newSingleThreadExecutor()

    private lateinit var locationManager: LocationManager

    private var locationListener: LocationListener? = null
    private var currentIntervalMs = 0L
    private var hasActiveTrip = false
    private var serviceStarted = false

    private val orderRefreshRunnable = object : Runnable {
        override fun run() {
            if (!serviceStarted) return

            refreshActiveOrders()
            handler.postDelayed(
                this,
                ORDER_REFRESH_INTERVAL_MS
            )
        }
    }

    override fun onCreate() {
        super.onCreate()

        locationManager = getSystemService(
            Context.LOCATION_SERVICE
        ) as LocationManager

        createNotificationChannel()
    }

    override fun onStartCommand(
        intent: Intent?,
        flags: Int,
        startId: Int
    ): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopGpsService()
                return START_NOT_STICKY
            }

            ACTION_START, null -> {
                if (!hasLocationPermission()) {
                    Log.w(TAG, "Нет разрешения на местоположение")
                    stopSelf()
                    return START_NOT_STICKY
                }

                if (!serviceStarted) {
                    startForegroundNotification()
                    serviceStarted = true

                    refreshActiveOrders()
                    handler.post(orderRefreshRunnable)
                }
            }
        }

        return START_STICKY
    }

    private fun startForegroundNotification() {
        val openAppIntent = Intent(
            this,
            MainActivity::class.java
        )

        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            openAppIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or
                PendingIntent.FLAG_IMMUTABLE
        )

        val notification = buildNotification(
            "Передача местоположения включена"
        )

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
            )
        } else {
            startForeground(
                NOTIFICATION_ID,
                notification
            )
        }
    }

    private fun buildNotification(message: String): Notification {
        val openAppIntent = Intent(
            this,
            MainActivity::class.java
        )

        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            openAppIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or
                PendingIntent.FLAG_IMMUTABLE
        )

        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_menu_mylocation)
                .setContentTitle("VEXA Driver")
                .setContentText(message)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .setCategory(Notification.CATEGORY_SERVICE)
                .build()
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
                .setSmallIcon(android.R.drawable.ic_menu_mylocation)
                .setContentTitle("VEXA Driver")
                .setContentText(message)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .build()
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return

        val channel = NotificationChannel(
            CHANNEL_ID,
            "Местоположение водителя",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description =
                "Фоновая передача координат водителя диспетчеру VEXA"
            setShowBadge(false)
        }

        val manager = getSystemService(
            NotificationManager::class.java
        )

        manager.createNotificationChannel(channel)
    }

    private fun refreshActiveOrders() {
        networkExecutor.execute {
            try {
                val response = DriverApiClient.getActiveOrders()
                val orders = response.optJSONArray("orders")

                val active = orders != null && orders.length() > 0

                handler.post {
                    if (!serviceStarted) return@post

                    if (hasActiveTrip != active) {
                        hasActiveTrip = active

                        val interval = if (active) {
                            TRIP_INTERVAL_MS
                        } else {
                            IDLE_INTERVAL_MS
                        }

                        updateLocationInterval(interval)

                        val message = if (active) {
                            "Заказ выполняется. GPS обновляется каждые 5 секунд"
                        } else {
                            "Вы на линии. GPS обновляется каждые 30 секунд"
                        }

                        updateNotification(message)
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Не удалось проверить активные заказы", e)
            }
        }
    }

    private fun updateNotification(message: String) {
        val manager = getSystemService(
            NotificationManager::class.java
        )

        manager.notify(
            NOTIFICATION_ID,
            buildNotification(message)
        )
    }

    private fun updateLocationInterval(intervalMs: Long) {
        if (!serviceStarted || currentIntervalMs == intervalMs) {
            return
        }

        if (!hasLocationPermission()) {
            stopGpsService()
            return
        }

        removeLocationUpdates()

        val provider = selectProvider()

        if (provider == null) {
            Log.w(TAG, "Нет доступного провайдера местоположения")
            return
        }

        val listener = object : LocationListener {
            override fun onLocationChanged(location: Location) {
                sendLocationToServer(location)
            }

            @Deprecated("Deprecated by Android")
            override fun onStatusChanged(
                provider: String?,
                status: Int,
                extras: Bundle?
            ) {
            }

            override fun onProviderEnabled(provider: String) {
            }

            override fun onProviderDisabled(provider: String) {
            }
        }

        try {
            locationManager.requestLocationUpdates(
                provider,
                intervalMs,
                0f,
                listener,
                Looper.getMainLooper()
            )

            locationListener = listener
            currentIntervalMs = intervalMs

            locationManager.getLastKnownLocation(provider)?.let {
                sendLocationToServer(it)
            }

            Log.i(
                TAG,
                "GPS-интервал установлен: ${intervalMs / 1000} секунд"
            )
        } catch (e: SecurityException) {
            Log.e(TAG, "Нет разрешения на получение координат", e)
            stopGpsService()
        } catch (e: Exception) {
            Log.e(TAG, "Ошибка запуска GPS", e)
        }
    }

    private fun selectProvider(): String? {
        val fineGranted = checkSelfPermission(
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        val coarseGranted = checkSelfPermission(
            Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        if (!fineGranted && !coarseGranted) return null

        return try {
            when {
                fineGranted && locationManager.isProviderEnabled(
                    LocationManager.GPS_PROVIDER
                ) -> LocationManager.GPS_PROVIDER

                locationManager.isProviderEnabled(
                    LocationManager.NETWORK_PROVIDER
                ) -> LocationManager.NETWORK_PROVIDER

                else -> null
            }
        } catch (e: Exception) {
            Log.e(TAG, "Ошибка выбора GPS-провайдера", e)
            null
        }
    }

    private fun hasLocationPermission(): Boolean {
        val fineGranted = checkSelfPermission(
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        val coarseGranted = checkSelfPermission(
            Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        return fineGranted || coarseGranted
    }

    private fun sendLocationToServer(location: Location) {
        networkExecutor.execute {
            try {
                DriverApiClient.sendLocation(
                    latitude = location.latitude,
                    longitude = location.longitude,
                    accuracyMeters = if (location.hasAccuracy()) {
                        location.accuracy.toDouble()
                    } else {
                        null
                    }
                )

                Log.d(
                    TAG,
                    "Координаты переданы: " +
                        "${location.latitude}, ${location.longitude}"
                )
            } catch (e: Exception) {
                Log.e(TAG, "Ошибка передачи координат", e)
            }
        }
    }

    private fun removeLocationUpdates() {
        locationListener?.let { listener ->
            try {
                locationManager.removeUpdates(listener)
            } catch (e: Exception) {
                Log.e(TAG, "Ошибка остановки GPS-обновлений", e)
            }
        }

        locationListener = null
        currentIntervalMs = 0L
    }

    private fun stopGpsService() {
        serviceStarted = false

        handler.removeCallbacks(orderRefreshRunnable)
        removeLocationUpdates()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            stopForeground(STOP_FOREGROUND_REMOVE)
        } else {
            @Suppress("DEPRECATION")
            stopForeground(true)
        }

        stopSelf()
    }

    override fun onDestroy() {
        serviceStarted = false

        handler.removeCallbacksAndMessages(null)
        removeLocationUpdates()

        networkExecutor.shutdownNow()

        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }
}
