
package ru.vexa.driver

import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL

/**
 * Сетевой клиент приложения VEXA Driver.
 *
 * Все методы выполняют синхронные HTTP-запросы.
 * Вызывать их необходимо в фоновом потоке, не в главном UI-потоке.
 */
object DriverApiClient {

    private const val BASE_URL = "https://109.120.184.20"

    @Volatile
    private var accessToken: String? = null

    /**
     * Сохранить токен авторизации водителя.
     */
    fun setAccessToken(token: String) {
        accessToken = token.trim().takeIf { it.isNotEmpty() }
    }

    /**
     * Получить текущий токен.
     */
    fun getAccessToken(): String? {
        return accessToken
    }

    /**
     * Очистить авторизацию.
     */
    fun clearAccessToken() {
        accessToken = null
    }

    /**
     * Экранирование строки для JSON.
     */
    private fun jsonString(value: String): String {
        return JSONObject.quote(value)
    }

    /**
     * Универсальный HTTP-запрос.
     */
    private fun request(
        path: String,
        method: String = "GET",
        body: String? = null,
        requiresAuth: Boolean = true
    ): String {

        val connection = URL("$BASE_URL$path")
            .openConnection() as HttpURLConnection

        try {
            connection.requestMethod = method
            connection.connectTimeout = 20000
            connection.readTimeout = 30000
            connection.setRequestProperty(
                "Accept",
                "application/json"
            )

            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty(
                    "Content-Type",
                    "application/json; charset=utf-8"
                )
            }

            if (requiresAuth) {
                val token = accessToken
                    ?: throw IllegalStateException(
                        "Необходимо авторизоваться"
                    )

                connection.setRequestProperty(
                    "Authorization",
                    "Bearer $token"
                )
            }

            if (body != null) {
                connection.outputStream.use { output ->
                    output.write(body.toByteArray(Charsets.UTF_8))
                }
            }

            val responseCode = connection.responseCode

            val responseStream = if (responseCode in 200..299) {
                connection.inputStream
            } else {
                connection.errorStream
            }

            val responseBody = responseStream
                ?.bufferedReader(Charsets.UTF_8)
                ?.use(BufferedReader::readText)
                .orEmpty()

            if (responseCode !in 200..299) {
                val detail = try {
                    JSONObject(responseBody).optString(
                        "detail",
                        responseBody
                    )
                } catch (_: Exception) {
                    responseBody
                }

                throw Exception(
                    "Ошибка сервера $responseCode: $detail"
                )
            }

            return responseBody

        } finally {
            connection.disconnect()
        }
    }

    /**
     * Авторизация водителя.
     *
     * POST /api/v1/driver/auth/login
     *
     * В ответе сервер возвращает access_token.
     */
    fun login(
        login: String,
        password: String
    ): String {

        require(login.isNotBlank()) {
            "Введите логин или телефон"
        }

        require(password.isNotBlank()) {
            "Введите пароль"
        }

        val json = """
            {
                "login": ${jsonString(login.trim())},
                "password": ${jsonString(password)}
            }
        """.trimIndent()

        val response = request(
            path = "/api/v1/driver/auth/login",
            method = "POST",
            body = json,
            requiresAuth = false
        )

        val token = JSONObject(response)
            .optString("access_token")
            .trim()

        if (token.isEmpty()) {
            throw Exception(
                "Сервер не вернул токен авторизации"
            )
        }

        setAccessToken(token)

        return token
    }

    /**
     * Получить профиль авторизованного водителя.
     *
     * GET /api/v1/driver/me
     */
    fun getProfile(): JSONObject {
        val response = request(
            path = "/api/v1/driver/me"
        )

        return JSONObject(response)
    }

    /**
     * Переключить режим водителя:
     * true — на линии;
     * false — не на линии.
     *
     * POST /api/v1/driver/online
     */
    fun setOnline(isOnline: Boolean): JSONObject {
        val json = JSONObject()
            .put("is_online", isOnline)
            .toString()

        val response = request(
            path = "/api/v1/driver/online",
            method = "POST",
            body = json
        )

        return JSONObject(response)
    }

    /**
     * Получить активные заказы водителя.
     *
     * GET /api/v1/driver/orders/active
     */
    fun getActiveOrders(): JSONObject {
        val response = request(
            path = "/api/v1/driver/orders/active"
        )

        return JSONObject(response)
    }

    /**
     * Изменить статус поездки.
     *
     * Возможные переходы:
     * assigned -> arrived
     * arrived -> in_progress
     * in_progress -> completed
     */
    fun updateOrderStatus(
        orderId: String,
        status: String
    ): JSONObject {

        require(orderId.isNotBlank()) {
            "Не указан номер заказа"
        }

        val json = JSONObject()
            .put("status", status)
            .toString()

        val response = request(
            path = "/api/v1/driver/orders/$orderId/status",
            method = "POST",
            body = json
        )

        return JSONObject(response)
    }

    /**
     * Передать координаты водителя.
     *
     * POST /api/v1/driver/location
     */
    fun sendLocation(
        latitude: Double,
        longitude: Double,
        accuracyMeters: Double? = null
    ): JSONObject {

        require(latitude in -90.0..90.0) {
            "Некорректная широта"
        }

        require(longitude in -180.0..180.0) {
            "Некорректная долгота"
        }

        val json = JSONObject()
            .put("latitude", latitude)
            .put("longitude", longitude)
            .apply {
                if (accuracyMeters != null) {
                    put("accuracy_meters", accuracyMeters)
                }
            }
            .toString()

        val response = request(
            path = "/api/v1/driver/location",
            method = "POST",
            body = json
        )

        return JSONObject(response)
    }
}
