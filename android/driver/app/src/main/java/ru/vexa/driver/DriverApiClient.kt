
package ru.vexa.driver

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Сетевой клиент приложения VEXA Driver.
 *
 * Все методы выполняют синхронные HTTP-запросы.
 * Вызывать их необходимо в фоновом потоке, не в главном UI-потоке.
 */
class DriverApiHttpException(
    val statusCode: Int,
    detail: String
) : Exception("Ошибка сервера $statusCode: $detail")

object DriverApiClient {

    private const val BASE_URL = "https://109.120.184.20"

    @Volatile
    private var accessToken: String? = null

    fun setAccessToken(token: String) {
        accessToken = token.trim().takeIf { it.isNotEmpty() }
    }

    fun getAccessToken(): String? {
        return accessToken
    }

    fun clearAccessToken() {
        accessToken = null
    }

    private fun jsonString(value: String): String {
        return JSONObject.quote(value)
    }

    private fun request(
        path: String,
        method: String = "GET",
        body: String? = null,
        requiresAuth: Boolean = true,
        connectTimeoutMs: Int = 20000,
        readTimeoutMs: Int = 30000
    ): String {
        val connection = URL("$BASE_URL$path")
            .openConnection() as HttpURLConnection

        try {
            connection.requestMethod = method
            connection.connectTimeout = connectTimeoutMs
            connection.readTimeout = readTimeoutMs

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
                ?.use { it.readText() }
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

                throw DriverApiHttpException(
                    statusCode = responseCode,
                    detail = detail
                )
            }

            return responseBody
        } finally {
            connection.disconnect()
        }
    }

    /**
     * Авторизация водителя.
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
     * Получить профиль водителя.
     */
    fun getProfile(): JSONObject {
        val response = request(
            path = "/api/v1/driver/me"
        )

        return JSONObject(response)
    }

    /**
     * Переключить режим водителя.
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
     * Получить активные заказы.
     */
    fun getActiveOrders(): JSONObject {
        val response = request(
            path = "/api/v1/driver/orders/active"
        )

        return JSONObject(response)
    }

    /**
     * Получить предложения новых заказов.
     *
     * GET /api/v1/driver/orders/offers
     *
     * Ответ сервера:
     * offers_count — количество предложений;
     * offers — массив предложений.
     *
     * Каждый элемент offers содержит:
     * offer_id — идентификатор предложения;
     * attempt_number — номер попытки;
     * response_timeout_seconds — время на ответ;
     * offered_at — время создания предложения;
     * expires_at — время окончания предложения;
     * distance_to_pickup_meters — расстояние до подачи;
     * order — информация о заказе.
     */
    fun getOrderOffers(): JSONObject {
        val response = request(
            path = "/api/v1/driver/orders/offers",
            connectTimeoutMs = 5000,
            readTimeoutMs = 5000
        )

        return JSONObject(response)
    }

    /**
     * Принять предложение заказа.
     *
     * POST /api/v1/driver/orders/offers/{offer_id}/accept
     */
    fun acceptOrderOffer(offerId: String): JSONObject {
        require(offerId.isNotBlank()) {
            "Не указан идентификатор предложения"
        }

        val response = request(
            path = "/api/v1/driver/orders/offers/$offerId/accept",
            method = "POST"
        )

        return JSONObject(response)
    }

    /**
     * Отклонить предложение заказа.
     *
     * POST /api/v1/driver/orders/offers/{offer_id}/reject
     */
    fun rejectOrderOffer(offerId: String): JSONObject {
        require(offerId.isNotBlank()) {
            "Не указан идентификатор предложения"
        }

        val response = request(
            path = "/api/v1/driver/orders/offers/$offerId/reject",
            method = "POST"
        )

        return JSONObject(response)
    }

    /**
     * Получить карточку заказа из истории кошелька.
     *
     * GET /api/v1/driver/orders/{order_id}
     * Сервер проверяет, что заказ принадлежит текущему водителю
     * и относится к его городу.
     */
    fun getOrder(orderId: String): JSONObject {
        require(orderId.isNotBlank()) {
            "Не указан номер заказа"
        }

        val response = request(
            path = "/api/v1/driver/orders/$orderId"
        )

        return JSONObject(response).optJSONObject("order")
            ?: throw Exception("Сервер не вернул карточку заказа")
    }

    /**
     * Изменить статус поездки.
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

    /**
     * Получить текущий кошелёк водителя.
     *
     * GET /api/v1/driver/wallet
     *
     * Ответ содержит:
     * balance_kopecks — текущий баланс, включая отрицательный;
     * reserved_kopecks — зарезервированная сумма;
     * available_kopecks — доступная к выводу сумма;
     * payouts — параметры и остаток дневного лимита.
     */
    fun getWallet(): JSONObject {
        val response = request(
            path = "/api/v1/driver/wallet"
        )

        return JSONObject(response)
    }

    /**
     * Получить историю операций кошелька.
     *
     * GET /api/v1/driver/wallet/transactions
     *
     * Ответ содержит:
     * order_public_number — номер заказа;
     * balance_change_kopecks — изменение баланса;
     * balance_after_kopecks — баланс после операции;
     * description — описание операции;
     * created_at — дата и время операции.
     */
    fun getWalletTransactions(
        limit: Int = 50,
        offset: Int = 0
    ): JSONObject {
        require(limit in 1..100) {
            "Количество записей должно быть от 1 до 100"
        }

        require(offset >= 0) {
            "Смещение не может быть отрицательным"
        }

        val response = request(
            path = "/api/v1/driver/wallet/transactions" +
                "?limit=$limit&offset=$offset"
        )

        return JSONObject(response)
    }

    /**
     * Получить финансовую сводку водителя.
     *
     * GET /api/v1/driver/finance
     */
    fun getFinanceSummary(): JSONObject {
        val response = request(
            path = "/api/v1/driver/finance"
        )

        return JSONObject(response)
    }

    /**
     * Получить историю финансовых операций водителя.
     *
     * GET /api/v1/driver/finance/transactions
     */
    fun getFinanceTransactions(
        limit: Int = 50,
        offset: Int = 0
    ): JSONObject {
        require(limit in 1..100) {
            "Количество записей должно быть от 1 до 100"
        }

        require(offset >= 0) {
            "Смещение не может быть отрицательным"
        }

        val response = request(
            path = "/api/v1/driver/finance/transactions" +
                "?limit=$limit&offset=$offset"
        )

        return JSONObject(response)
    }
}
