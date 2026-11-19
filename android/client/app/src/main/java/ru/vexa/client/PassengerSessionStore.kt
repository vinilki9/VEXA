
package ru.vexa.client

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Защищённое хранилище сессии пассажира.
 *
 * Данные шифруются AES-GCM.
 * Ключ шифрования хранится в Android Keystore
 * и не сохраняется в SharedPreferences.
 */
object PassengerSessionStore {

    private const val ANDROID_KEY_STORE = "AndroidKeyStore"
    private const val KEY_ALIAS = "vexa_passenger_session_key"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"
    private const val PREFS_NAME = "vexa_secure_passenger_session"
    private const val PREF_IV = "session_iv"
    private const val PREF_DATA = "session_data"
    private const val GCM_TAG_LENGTH_BITS = 128

    data class Session(
        val accessToken: String,
        val passengerPhone: String
    )

    /**
     * Сохранить токен и телефон одной зашифрованной записью.
     */
    @Synchronized
    fun saveSession(
        context: Context,
        accessToken: String,
        passengerPhone: String
    ) {
        val token = accessToken.trim()
        val phone = passengerPhone.trim()

        require(token.isNotEmpty()) {
            "Нельзя сохранить пустой токен авторизации"
        }

        require(phone.isNotEmpty()) {
            "Нельзя сохранить пустой номер телефона"
        }

        val payload = JSONObject().apply {
            put("access_token", token)
            put("passenger_phone", phone)
        }.toString()

        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateSecretKey())

        val encrypted = cipher.doFinal(
            payload.toByteArray(Charsets.UTF_8)
        )

        val prefs = context.applicationContext
            .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

        val saved = prefs.edit()
            .putString(
                PREF_IV,
                Base64.encodeToString(cipher.iv, Base64.NO_WRAP)
            )
            .putString(
                PREF_DATA,
                Base64.encodeToString(encrypted, Base64.NO_WRAP)
            )
            .commit()

        check(saved) {
            "Не удалось сохранить защищённую сессию VEXA"
        }
    }

    /**
     * Прочитать и расшифровать сохранённую сессию.
     *
     * При повреждении данных или недоступности ключа
     * сохранённая сессия очищается.
     */
    @Synchronized
    fun loadSession(context: Context): Session? {
        val prefs = context.applicationContext
            .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

        val ivEncoded = prefs.getString(PREF_IV, null)
            ?: return null

        val dataEncoded = prefs.getString(PREF_DATA, null)
            ?: run {
                clearSession(context)
                return null
            }

        return try {
            val iv = Base64.decode(ivEncoded, Base64.NO_WRAP)
            val encrypted = Base64.decode(
                dataEncoded,
                Base64.NO_WRAP
            )

            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(
                Cipher.DECRYPT_MODE,
                getOrCreateSecretKey(),
                GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv)
            )

            val decrypted = cipher.doFinal(encrypted)
            val json = JSONObject(
                String(decrypted, Charsets.UTF_8)
            )

            val token = json.optString("access_token").trim()
            val phone = json.optString("passenger_phone").trim()

            if (token.isEmpty() || phone.isEmpty()) {
                clearSession(context)
                null
            } else {
                Session(
                    accessToken = token,
                    passengerPhone = phone
                )
            }
        } catch (error: Exception) {
            clearSession(context)
            null
        }
    }

    /**
     * Удалить сессию и ключ шифрования.
     */
    @Synchronized
    fun clearSession(context: Context) {
        context.applicationContext
            .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .clear()
            .commit()

        val keyStore = KeyStore.getInstance(ANDROID_KEY_STORE)
        keyStore.load(null)

        if (keyStore.containsAlias(KEY_ALIAS)) {
            keyStore.deleteEntry(KEY_ALIAS)
        }
    }

    /**
     * Получить существующий AES-ключ или создать новый.
     */
    private fun getOrCreateSecretKey(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEY_STORE)
        keyStore.load(null)

        val existingKey = keyStore.getKey(KEY_ALIAS, null)
        if (existingKey is SecretKey) {
            return existingKey
        }

        val keyGenerator = KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,
            ANDROID_KEY_STORE
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
            .build()

        keyGenerator.init(keySpec)
        return keyGenerator.generateKey()
    }
}
