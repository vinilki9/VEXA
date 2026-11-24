
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
import java.util.concurrent.atomic.AtomicBoolean

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
        private const val OFFER_REFRESH_INTERVAL_MS = 2_000L
        private const val PROFILE_RETRY_INTERVAL_MS = 15_000L

        const val STATUS_PREFS = "vexa_driver_health"
        const val KEY_GPS_OK = "gps_ok"
        const val KEY_SERVER_OK = "server_ok"
        const val KEY_AUTH_OK = "auth_ok"
        const val KEY_ALERT = "alert"
        const val KEY_ALERT_ID = "alert_id"

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
    private val offersExecutor = Executors.newSingleThreadExecutor()

    private val offerRefreshInProgress = AtomicBoolean(false)
    private val profileCheckInProgress = AtomicBoolean(false)

    private lateinit var locationManager: LocationManager

    private var locationListener: LocationListener? = null
    private var currentIntervalMs = 0L
    private var hasActiveTrip = false
    private var serviceStarted = false
    private var driverOnlineConfirmed = false
    private var lastGpsWarningState: Boolean? = null
    private var lastServerWarningState: Boolean? = null

    private val profileCheckRunnable = object : Runnable {
        override fun run() {
            checkDriverSession()
        }
    }

    private val orderRefreshRunnable = object : Runnable {
        override fun run() {
            if (!serviceStarted || !driverOnlineConfirmed) return

            refreshActiveOrders()

            handler.postDelayed(
                this,
                ORDER_REFRESH_INTERVAL_MS
            )
        }
    }

    private val offerRefreshRunnable = object : Runnable {
        override fun run() {
            if (!serviceStarted || !driverOnlineConfirmed) return

            if (offerRefreshInProgress.compareAndSet(false, true)) {
                try {
                    offersExecutor.execute {
                        try {
                            val response = DriverApiClient.refreshOrderOffers()
                            // Звук, вибрация и уведомление только для нового ID.
                            if (serviceStarted && driverOnlineConfirmed) {
                                DriverOfferAlerts.onPoll(this@DriverLocationService, response)
                            }
                            setServerState(true)

                            Log.d(
                                TAG,
                                "Предложения заказов обновлены"
                            )
                        } catch (e: Exception) {
                            setServerState(false)
                            Log.e(
                                TAG,
                                "Не удалось обновить предложения заказов",
                                e
                            )
                        } finally {
                            offerRefreshInProgress.set(false)
                        }
                    }
                } catch (e: Exception) {
                    offerRefreshInProgress.set(false)
                    setServerState(false)

                    Log.e(
                        TAG,
                        "Не удалось запустить обновление предложений",
                        e
                    )
                }
            }

            handler.postDelayed(
                this,
                OFFER_REFRESH_INTERVAL_MS
            )
        }
    }

    private fun updateHealth(
        gpsOk: Boolean? = null,
        serverOk: Boolean? = null,
        authOk: Boolean? = null,
        alert: String? = null
    ) {
        val prefs = getSharedPreferences(STATUS_PREFS, Context.MODE_PRIVATE)
        val editor = prefs.edit()

        if (gpsOk != null) editor.putBoolean(KEY_GPS_OK, gpsOk)
        if (serverOk != null) editor.putBoolean(KEY_SERVER_OK, serverOk)
        if (authOk != null) editor.putBoolean(KEY_AUTH_OK, authOk)

        if (alert != null) {
            editor.putString(KEY_ALERT, alert)
            editor.putLong(KEY_ALERT_ID, System.currentTimeMillis())
        }

        editor.apply()
    }

    private fun setServerState(ok: Boolean) {
        updateHealth(serverOk = ok)

        if (lastServerWarningState == null || lastServerWarningState == ok) {
            lastServerWarningState = ok
            return
        }

        lastServerWarningState = ok
        updateHealth(
            alert = if (ok) "Связь с сервером восстановлена" else "Нет связи с сервером"
        )
    }

    private fun setGpsState(ok: Boolean) {
        updateHealth(gpsOk = ok)

        if (lastGpsWarningState == null || lastGpsWarningState == ok) {
            lastGpsWarningState = ok
            return
        }

        lastGpsWarningState = ok
        updateHealth(
            alert = if (ok) "GPS восстановлен" else "GPS недоступен"
        )
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
                    updateHealth(gpsOk = false, authOk = false)
                    stopSelf()
                    return START_NOT_STICKY
                }

                if (!serviceStarted) {
                    startForegroundNotification()
                    serviceStarted = true
                    driverOnlineConfirmed = false
                    updateHealth(
                        gpsOk = false,
                        serverOk = false,
                        authOk = !DriverApiClient.getAccessToken().isNullOrBlank()
                    )

                    Log.i(
                        TAG,
                        "Сервис запущен. Ожидается проверка авторизации и режима «На линии»"
                    )

                    scheduleProfileCheck(0L)
                } else if (!driverOnlineConfirmed) {
                    // Повторный запуск не должен создавать
                    // дополнительные циклы проверки и опроса.
                    scheduleProfileCheck(0L)
                }
            }
        }

        return START_STICKY
    }

    /**
     * Проверить авторизацию и актуальный статус водителя.
     *
     * GPS и опрос заказов запускаются только после подтверждения
     * действующей сессии и is_online=true.
     */
    private fun checkDriverSession() {
        if (!serviceStarted || driverOnlineConfirmed) return

        if (DriverApiClient.getAccessToken().isNullOrBlank()) {
            updateHealth(
                gpsOk = false,
                authOk = false,
                alert = "Требуется вход в профиль"
            )
            Log.w(TAG, "Нет токена авторизации. GPS-сервис остановлен")
            stopGpsService()
            return
        }

        if (!profileCheckInProgress.compareAndSet(false, true)) {
            return
        }

        try {
            networkExecutor.execute {
                try {
                    val profile = DriverApiClient.getProfile()
                    val isOnline = profile.optBoolean(
                        "is_online",
                        false
                    )
                    setServerState(true)
                    updateHealth(authOk = true)

                    handler.post {
                        profileCheckInProgress.set(false)

                        if (!serviceStarted) return@post

                        if (!isOnline) {
                            updateHealth(gpsOk = false)
                            Log.i(
                                TAG,
                                "Профиль подтверждён, но водитель не на линии"
                            )
                            stopGpsService()
                            return@post
                        }

                        startOnlineLoops()
                    }
                } catch (e: Exception) {
                    handler.post {
                        profileCheckInProgress.set(false)

                        if (!serviceStarted) return@post

                        if (
                            e is DriverApiHttpException &&
                            (e.statusCode == 401 || e.statusCode == 403)
                        ) {
                            updateHealth(
                                gpsOk = false,
                                serverOk = true,
                                authOk = false,
                                alert = "Требуется повторный вход"
                            )
                            Log.w(
                                TAG,
                                "Сервер отклонил авторизацию. GPS-сервис остановлен",
                                e
                            )
                            stopGpsService()
                            return@post
                        }

                        setServerState(false)
                        Log.w(
                            TAG,
                            "Не удалось проверить профиль. " +
                                "Повторная проверка через 15 секунд",
                            e
                        )

                        scheduleProfileCheck(
                            PROFILE_RETRY_INTERVAL_MS
                        )
                    }
                }
            }
        } catch (e: Exception) {
            profileCheckInProgress.set(false)
            setServerState(false)

            Log.e(
                TAG,
                "Не удалось запустить проверку профиля",
                e
            )

            scheduleProfileCheck(
                PROFILE_RETRY_INTERVAL_MS
            )
        }
    }

    private fun scheduleProfileCheck(delayMs: Long) {
        if (!serviceStarted || driverOnlineConfirmed) return

        handler.removeCallbacks(profileCheckRunnable)
        handler.postDelayed(
            profileCheckRunnable,
            delayMs
        )
    }

    /**
     * Запустить фоновые циклы только после подтверждения,
     * что водитель авторизован и находится на линии.
     */
    private fun startOnlineLoops() {
        if (!serviceStarted || driverOnlineConfirmed) return

        driverOnlineConfirmed = true
        updateHealth(authOk = true)

        Log.i(
            TAG,
            "Авторизация подтверждена. Водитель на линии. Запускаются GPS и опрос заказов"
        )

        updateNotification(
            "Вы на линии. GPS обновляется каждые 30 секунд"
        )

        // Начальный GPS-интервал для свободного водителя.
        updateLocationInterval(IDLE_INTERVAL_MS)

        // Проверяем наличие активной поездки.
        refreshActiveOrders()

        // Запускаем периодическую проверку активных заказов.
        handler.removeCallbacks(orderRefreshRunnable)
        handler.post(orderRefreshRunnable)

        // Запускаем опрос предложений заказов.
        handler.removeCallbacks(offerRefreshRunnable)
        handler.post(offerRefreshRunnable)
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
            "Проверка режима водителя"
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
        if (!serviceStarted || !driverOnlineConfirmed) return

        networkExecutor.execute {
            try {
                val response = DriverApiClient.getActiveOrders()
                val orders = response.optJSONArray("orders")

                val active = orders != null && orders.length() > 0

                handler.post {
                    if (!serviceStarted || !driverOnlineConfirmed) {
                        return@post
                    }

                    val tripStateChanged = hasActiveTrip != active
                    hasActiveTrip = active

                    val interval = if (active) {
                        TRIP_INTERVAL_MS
                    } else {
                        IDLE_INTERVAL_MS
                    }

                    // Повторная проверка интервала позволяет
                    // восстановить GPS, если провайдер был недоступен.
                    updateLocationInterval(interval)

                    if (tripStateChanged) {
                        val message = if (active) {
                            "Заказ выполняется. GPS обновляется каждые 5 секунд"
                        } else {
                            "Вы на линии. GPS обновляется каждые 30 секунд"
                        }

                        updateNotification(message)
                    }
                }
            } catch (e: Exception) {
                setServerState(false)
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
        if (
            !serviceStarted ||
            !driverOnlineConfirmed ||
            currentIntervalMs == intervalMs
        ) {
            return
        }

        if (!hasLocationPermission()) {
            stopGpsService()
            return
        }

        removeLocationUpdates()

        val provider = selectProvider()

        if (provider == null) {
            setGpsState(false)
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
                handler.post {
                    if (serviceStarted && driverOnlineConfirmed) {
                        updateLocationInterval(
                            if (hasActiveTrip) TRIP_INTERVAL_MS else IDLE_INTERVAL_MS
                        )
                    }
                }
            }

            override fun onProviderDisabled(provider: String) {
                currentIntervalMs = 0L
                setGpsState(false)
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
            setGpsState(false)
            Log.e(TAG, "Нет разрешения на получение координат", e)
            stopGpsService()
        } catch (e: Exception) {
            setGpsState(false)
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
        if (!serviceStarted || !driverOnlineConfirmed) return

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

                setServerState(true)
                setGpsState(true)

                Log.d(
                    TAG,
                    "Координаты переданы: " +
                        "${location.latitude}, ${location.longitude}"
                )
            } catch (e: Exception) {
                setServerState(false)
                setGpsState(false)
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
        DriverOfferAlerts.clearNotification(this)
        serviceStarted = false
        driverOnlineConfirmed = false
        updateHealth(gpsOk = false)

        handler.removeCallbacks(profileCheckRunnable)
        handler.removeCallbacks(orderRefreshRunnable)
        handler.removeCallbacks(offerRefreshRunnable)

        removeLocationUpdates()

        // Очищаем предложения при уходе водителя с линии
        // или при отсутствии действующей авторизации.
        DriverApiClient.clearCachedOrderOffers()

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
        driverOnlineConfirmed = false

        handler.removeCallbacksAndMessages(null)
        removeLocationUpdates()

        networkExecutor.shutdownNow()
        offersExecutor.shutdownNow()

        // Не оставляем старые предложения после остановки сервиса.
        DriverApiClient.clearCachedOrderOffers()

        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }
}
