
package ru.vexa.driver

import android.content.Context
import android.content.SharedPreferences
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

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

    private val BASE_URL = BuildConfig.VEXA_API_BASE_URL

    private const val KEYSTORE_PROVIDER = "AndroidKeyStore"
    private const val KEY_ALIAS = "vexa_driver_access_token_key_v1"

    private const val TOKEN_PREFS = "vexa_secure_session"
    private const val TOKEN_CIPHER_TEXT_KEY = "access_token_ciphertext"
    private const val TOKEN_IV_KEY = "access_token_iv"

    private const val GCM_TAG_LENGTH_BITS = 128

    private val tokenLock = Any()
    private val offersCacheLock = Any()

    @Volatile
    private var accessToken: String? = null

    @Volatile
    private var applicationContext: Context? = null

    @Volatile
    private var cachedOrderOffers: JSONObject? = null

    @Volatile
    private var cachedOrderOffersError: Exception? = null

    /**
     * Инициализировать защищённое хранилище сессии.
     *
     * Вызывать из Application.onCreate() до запуска Activity
     * и фоновых сервисов.
     *
     * Токен восстанавливается из зашифрованного хранилища.
     * В случае ошибки повреждённая сессия удаляется.
     */
    fun initialize(context: Context) {
        synchronized(tokenLock) {
            applicationContext = context.applicationContext

            try {
                val prefs = getTokenPreferences()
                val encryptedToken = prefs.getString(
                    TOKEN_CIPHER_TEXT_KEY,
                    null
                )
                val encodedIv = prefs.getString(
                    TOKEN_IV_KEY,
                    null
                )

                if (encryptedToken.isNullOrBlank() || encodedIv.isNullOrBlank()) {
                    accessToken = null
                    return
                }

                val ciphertext = Base64.decode(
                    encryptedToken,
                    Base64.NO_WRAP
                )

                val iv = Base64.decode(
                    encodedIv,
                    Base64.NO_WRAP
                )

                accessToken = decryptToken(ciphertext, iv)
                    .trim()
                    .takeIf { it.isNotEmpty() }
            } catch (_: Exception) {
                accessToken = null
                clearStoredToken(deleteKey = true)
            }
        }
    }

    /**
     * Получить настройки защищённого хранилища.
     */
    private fun getTokenPreferences(): SharedPreferences {
        val context = applicationContext
            ?: throw IllegalStateException(
                "Защищённое хранилище не инициализировано"
            )

        return context.getSharedPreferences(
            TOKEN_PREFS,
            Context.MODE_PRIVATE
        )
    }

    /**
     * Получить ключ AES из Android Keystore.
     * Если ключ ещё не создан, создать новый AES-256 ключ.
     */
    private fun getOrCreateSecretKey(): SecretKey {
        val keyStore = KeyStore.getInstance(KEYSTORE_PROVIDER)
        keyStore.load(null)

        val existingKey = keyStore.getKey(
            KEY_ALIAS,
            null
        ) as? SecretKey

        if (existingKey != null) {
            return existingKey
        }

        val keyGenerator = KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,
            KEYSTORE_PROVIDER
        )

        val keySpec = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or
                KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(
                KeyProperties.ENCRYPTION_PADDING_NONE
            )
            .setRandomizedEncryptionRequired(true)
            .setKeySize(256)
            .build()

        keyGenerator.init(keySpec)

        return keyGenerator.generateKey()
    }

    /**
     * Зашифровать токен с использованием AES/GCM.
     */
    private fun encryptToken(token: String): Pair<ByteArray, ByteArray> {
        val secretKey = getOrCreateSecretKey()

        val cipher = Cipher.getInstance("AES/GCM/NoPadding")

        cipher.init(
            Cipher.ENCRYPT_MODE,
            secretKey
        )

        val ciphertext = cipher.doFinal(
            token.toByteArray(Charsets.UTF_8)
        )

        val iv = cipher.iv

        return Pair(ciphertext, iv)
    }

    /**
     * Расшифровать токен с использованием AES/GCM.
     */
    private fun decryptToken(
        ciphertext: ByteArray,
        iv: ByteArray
    ): String {
        val secretKey = getOrCreateSecretKey()

        val cipher = Cipher.getInstance("AES/GCM/NoPadding")

        val parameters = GCMParameterSpec(
            GCM_TAG_LENGTH_BITS,
            iv
        )

        cipher.init(
            Cipher.DECRYPT_MODE,
            secretKey,
            parameters
        )

        val plaintext = cipher.doFinal(ciphertext)

        return String(
            plaintext,
            Charsets.UTF_8
        )
    }

    /**
     * Сохранить зашифрованный токен в приватном хранилище.
     *
     * Открытый токен в SharedPreferences не сохраняется.
     */
    private fun saveEncryptedToken(token: String) {
        val (ciphertext, iv) = encryptToken(token)

        val encryptedToken = Base64.encodeToString(
            ciphertext,
            Base64.NO_WRAP
        )

        val encodedIv = Base64.encodeToString(
            iv,
            Base64.NO_WRAP
        )

        val saved = getTokenPreferences()
            .edit()
            .putString(
                TOKEN_CIPHER_TEXT_KEY,
                encryptedToken
            )
            .putString(
                TOKEN_IV_KEY,
                encodedIv
            )
            .commit()

        if (!saved) {
            throw IllegalStateException(
                "Не удалось сохранить защищённую сессию"
            )
        }
    }

    /**
     * Удалить сохранённый токен.
     *
     * При необходимости также удалить ключ Android Keystore.
     */
    private fun clearStoredToken(deleteKey: Boolean) {
        try {
            getTokenPreferences()
                .edit()
                .remove(TOKEN_CIPHER_TEXT_KEY)
                .remove(TOKEN_IV_KEY)
                .commit()
        } catch (_: Exception) {
            // Продолжаем очистку ключа даже при ошибке Preferences.
        }

        if (deleteKey) {
            try {
                val keyStore = KeyStore.getInstance(
                    KEYSTORE_PROVIDER
                )

                keyStore.load(null)

                if (keyStore.containsAlias(KEY_ALIAS)) {
                    keyStore.deleteEntry(KEY_ALIAS)
                }
            } catch (_: Exception) {
                // Ошибка удаления ключа не должна прерывать выход.
            }
        }
    }

    /**
     * Установить токен авторизации.
     *
     * Сначала токен сохраняется в зашифрованном виде,
     * затем устанавливается в памяти приложения.
     */
    fun setAccessToken(token: String) {
        synchronized(tokenLock) {
            val normalizedToken = token.trim()
                .takeIf { it.isNotEmpty() }

            if (normalizedToken == null) {
                accessToken = null
                clearStoredToken(deleteKey = true)
                return
            }

            saveEncryptedToken(normalizedToken)

            // Не показывать предложения предыдущего водителя после смены сессии.
            if (accessToken != normalizedToken) {
                clearCachedOrderOffers()
            }
            accessToken = normalizedToken
        }
    }

    /**
     * Получить текущий токен авторизации из памяти.
     */
    fun getAccessToken(): String? {
        return accessToken
    }

    /**
     * Полностью очистить сессию авторизации.
     *
     * Удаляется токен из памяти, зашифрованное значение
     * из SharedPreferences и ключ из Android Keystore.
     */
    fun clearAccessToken() {
        synchronized(tokenLock) {
            accessToken = null
            clearStoredToken(deleteKey = true)
        }

        clearCachedOrderOffers()
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
     * Получить предложения новых заказов из локального кэша.
     *
     * Этот метод не выполняет сетевых запросов.
     * Его вызывает MainActivity для чтения данных,
     * которые обновляет DriverLocationService.
     *
     * Если фоновый сервис ещё не получил ответ сервера,
     * возвращается пустой список предложений.
     *
     * Если последний запрос завершился ошибкой,
     * повторно выбрасывается сохранённая ошибка,
     * чтобы MainActivity могла показать корректное сообщение.
     */
    fun getOrderOffers(): JSONObject {
        synchronized(offersCacheLock) {
            cachedOrderOffersError?.let {
                throw it
            }

            val cached = cachedOrderOffers
                ?: return JSONObject(
                    """{"offers_count":0,"offers":[]}"""
                )

            return JSONObject(cached.toString())
        }
    }

    /**
     * Получить предложения новых заказов непосредственно с сервера.
     *
     * GET /api/v1/driver/orders/offers
     *
     * Вызывать только из фонового DriverLocationService.
     * Успешный ответ сохраняется в общем кэше приложения.
     * Ошибка сохраняется и передаётся MainActivity через getOrderOffers().
     */
    fun refreshOrderOffers(): JSONObject {
        try {
            val response = request(
                path = "/api/v1/driver/orders/offers",
                connectTimeoutMs = 5000,
                readTimeoutMs = 5000
            )

            val result = JSONObject(response)

            synchronized(offersCacheLock) {
                cachedOrderOffers = JSONObject(result.toString())
                cachedOrderOffersError = null
            }

            return result
        } catch (e: Exception) {
            synchronized(offersCacheLock) {
                cachedOrderOffersError = e
            }

            throw e
        }
    }

    /**
     * Очистить кэш предложений заказов и сохранённую ошибку.
     *
     * Вызывать при уходе водителя с линии,
     * остановке фонового опроса или выходе из аккаунта.
     */
    fun clearCachedOrderOffers() {
        synchronized(offersCacheLock) {
            cachedOrderOffers = null
            cachedOrderOffersError = null
        }
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

        // Даже при потере ответа сервер мог уже обработать действие.
        // Скрываем старый список и ждём следующего опроса.
        try {
            val response = request(
                path = "/api/v1/driver/orders/offers/$offerId/accept",
                method = "POST"
            )
            return JSONObject(response)
        } finally {
            clearCachedOrderOffers()
        }
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

        // Даже при потере ответа сервер мог уже обработать действие.
        // Скрываем старый список и ждём следующего опроса.
        try {
            val response = request(
                path = "/api/v1/driver/orders/offers/$offerId/reject",
                method = "POST"
            )
            return JSONObject(response)
        } finally {
            clearCachedOrderOffers()
        }
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
        require(status in setOf("arrived", "in_progress", "completed")) {
            "Недопустимый статус поездки"
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
