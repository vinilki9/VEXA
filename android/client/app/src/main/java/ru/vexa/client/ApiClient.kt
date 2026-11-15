
package ru.vexa.client

import java.util.UUID
import java.util.concurrent.TimeUnit

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

object ApiClient {

    private const val BASE_URL = "https://109.120.184.20"

    private val JSON_MEDIA_TYPE =
        "application/json; charset=utf-8".toMediaType()

    @Volatile
    private var accessToken: String? = null

    val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    /**
     * Сохранить JWT-токен авторизованного пассажира.
     */
    fun setAccessToken(token: String) {
        accessToken = token.trim().takeIf { it.isNotEmpty() }
    }

    /**
     * Получить текущий JWT-токен.
     */
    fun getAccessToken(): String? {
        return accessToken
    }

    /**
     * Завершить текущую авторизацию в памяти приложения.
     */
    fun clearAccessToken() {
        accessToken = null
    }

    /**
     * Экранирование строки для JSON.
     */
    private fun jsonString(value: String): String {
        val escaped = value
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\b", "\\b")
            .replace("\u000C", "\\f")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")

        return "\"$escaped\""
    }

    /**
     * Выполнить HTTP-запрос и вернуть тело ответа.
     */
    private suspend fun executeRequest(
        request: Request
    ): String {
        return withContext(Dispatchers.IO) {
            client.newCall(request).execute().use { response ->
                val result = response.body?.string().orEmpty()

                if (!response.isSuccessful) {
                    throw Exception(
                        "Ошибка сервера: ${response.code} $result"
                    )
                }

                result
            }
        }
    }

    /**
     * Запросить SMS-авторизацию пассажира.
     *
     * POST /api/v1/auth/passenger/request
     *
     * Возвращает JSON с session_id и status.
     */
    suspend fun requestPassengerAuth(
        phone: String
    ): String {
        val json = """
            {
                "phone": ${jsonString(phone)}
            }
        """.trimIndent()

        val request = Request.Builder()
            .url("$BASE_URL/api/v1/auth/passenger/request")
            .post(
                json.toRequestBody(JSON_MEDIA_TYPE)
            )
            .build()

        return executeRequest(request)
    }

    /**
     * Проверить состояние SMS-авторизации.
     *
     * GET /api/v1/auth/passenger/sessions/{session_id}
     *
     * При подтверждённой авторизации сервер возвращает access_token.
     */
    suspend fun getPassengerAuthStatus(
        sessionId: String
    ): String {
        val request = Request.Builder()
            .url(
                "$BASE_URL/api/v1/auth/passenger/sessions/$sessionId"
            )
            .get()
            .build()

        return executeRequest(request)
    }

    /**
     * Передать SMS-код для проверки.
     *
     * POST /api/v1/auth/passenger/verify
     *
     * После проверки необходимо отдельно запросить статус сессии.
     * Сам ответ verify не считается подтверждением авторизации.
     */
    suspend fun verifyPassengerAuth(
        sessionId: String,
        code: String
    ): String {
        val json = """
            {
                "session_id": ${jsonString(sessionId)},
                "code": ${jsonString(code)}
            }
        """.trimIndent()

        val request = Request.Builder()
            .url("$BASE_URL/api/v1/auth/passenger/verify")
            .post(
                json.toRequestBody(JSON_MEDIA_TYPE)
            )
            .build()

        return executeRequest(request)
    }

    /**
     * Отправить заказ на сервер VEXA.
     *
     * POST /api/v1/orders
     *
     * Требуется подтверждённая авторизация пассажира.
     * Цена рассчитывается сервером, а не приложением.
     *
     * Для защиты от повторной отправки используется
     * Idempotency-Key.
     */
    suspend fun sendOrder(
        json: String,
        idempotencyKey: String = UUID.randomUUID().toString()
    ): String {
        val token = accessToken
            ?: throw IllegalStateException(
                "Для оформления заказа необходимо войти в профиль"
            )

        val body = json.toRequestBody(JSON_MEDIA_TYPE)

        val request = Request.Builder()
            .url("$BASE_URL/api/v1/orders")
            .header(
                "Authorization",
                "Bearer $token"
            )
            .header(
                "Idempotency-Key",
                idempotencyKey
            )
            .post(body)
            .build()

        return executeRequest(request)
    }

    /**
     * Получить историю заказов пассажира.
     *
     * GET /api/v1/passenger/orders
     */
    suspend fun getPassengerOrders(): String {
        val token = accessToken
            ?: throw IllegalStateException(
                "Для просмотра заказов необходимо войти в профиль"
            )

        val request = Request.Builder()
            .url("$BASE_URL/api/v1/passenger/orders")
            .header(
                "Authorization",
                "Bearer $token"
            )
            .get()
            .build()

        return executeRequest(request)
    }
}
