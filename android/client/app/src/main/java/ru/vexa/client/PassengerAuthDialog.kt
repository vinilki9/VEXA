
package ru.vexa.client

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import org.json.JSONObject

@Composable
fun PassengerAuthDialog(
    onAuthenticated: () -> Unit,
    onDismiss: () -> Unit
) {
    var phone by remember { mutableStateOf("") }
    var code by remember { mutableStateOf("") }

    var sessionId by remember { mutableStateOf<String?>(null) }
    var authStatus by remember { mutableStateOf("idle") }

    var loading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    fun processStatus(response: String) {
        val json = JSONObject(response)
        val status = json.optString("status", "pending")

        authStatus = status

        if (status == "verified") {
            val token = json.optString("access_token", "")

            if (token.isNotBlank()) {
                ApiClient.setPassengerSession(token, phone.trim())
                onAuthenticated()
            } else {
                authStatus = "failed"
                errorMessage = "Сервер не вернул токен авторизации"
            }
        } else if (status == "failed") {
            errorMessage = "Не удалось подтвердить номер телефона"
        }
    }

    LaunchedEffect(sessionId, authStatus) {
        val currentSession = sessionId ?: return@LaunchedEffect

        if (
            authStatus != "pending" &&
            authStatus != "checking"
        ) {
            return@LaunchedEffect
        }

        loading = true

        try {
            repeat(45) {
                delay(2000)

                val response = ApiClient.getPassengerAuthStatus(
                    currentSession
                )

                processStatus(response)

                if (
                    authStatus == "verified" ||
                    authStatus == "failed" ||
                    authStatus == "otp_required"
                ) {
                    return@LaunchedEffect
                }
            }

            if (
                authStatus == "pending" ||
                authStatus == "checking"
            ) {
                errorMessage =
                    "Не удалось подтвердить авторизацию за отведённое время. Попробуйте проверить статус ещё раз."
            }
        } catch (error: Exception) {
            errorMessage = error.message
                ?: "Ошибка проверки авторизации"
        } finally {
            loading = false
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text("Вход в профиль VEXA")
        },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                if (sessionId == null) {
                    Text(
                        "Введите номер телефона. На него будет отправлен запрос подтверждения."
                    )

                    OutlinedTextField(
                        value = phone,
                        onValueChange = {
                            phone = it.filter { char ->
                                char.isDigit() ||
                                    char == '+' ||
                                    char == ' ' ||
                                    char == '-' ||
                                    char == '(' ||
                                    char == ')'
                            }
                            errorMessage = null
                        },
                        modifier = Modifier.fillMaxWidth(),
                        label = {
                            Text("Номер телефона")
                        },
                        singleLine = true
                    )
                } else {
                    when (authStatus) {
                        "otp_required" -> {
                            Text(
                                "Введите код подтверждения из SMS."
                            )

                            OutlinedTextField(
                                value = code,
                                onValueChange = {
                                    code = it.filter(Char::isDigit)
                                        .take(8)
                                    errorMessage = null
                                },
                                modifier = Modifier.fillMaxWidth(),
                                label = {
                                    Text("Код подтверждения")
                                },
                                singleLine = true
                            )
                        }

                        "verified" -> {
                            Text("Номер телефона подтверждён.")
                        }

                        "failed" -> {
                            Text(
                                "Авторизация не завершена. Попробуйте войти заново."
                            )
                        }

                        else -> {
                            Text(
                                "Ожидаем подтверждения номера телефона..."
                            )
                        }
                    }
                }

                if (loading) {
                    CircularProgressIndicator()
                }

                errorMessage?.let {
                    Text(
                        text = it,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
        },
        confirmButton = {
            if (sessionId == null) {
                Button(
                    enabled = !loading &&
                        phone.count { it.isDigit() } >= 10,
                    onClick = {
                        loading = true
                        errorMessage = null
                        authStatus = "starting"
                    }
                ) {
                    Text("Получить код")
                }
            } else if (authStatus == "otp_required") {
                Button(
                    enabled = !loading && code.length >= 4,
                    onClick = {
                        loading = true
                        errorMessage = null
                        authStatus = "checking"
                    }
                ) {
                    Text("Подтвердить")
                }
            } else if (authStatus == "failed") {
                Button(
                    onClick = {
                        sessionId = null
                        authStatus = "idle"
                        code = ""
                        errorMessage = null
                    }
                ) {
                    Text("Попробовать снова")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Закрыть")
            }
        }
    )

    LaunchedEffect(authStatus) {
        if (authStatus == "starting") {
            try {
                loading = true

                val response = ApiClient.requestPassengerAuth(phone)
                val json = JSONObject(response)

                val newSessionId = json.optString("session_id")

                if (newSessionId.isBlank()) {
                    throw IllegalStateException(
                        "Сервер не вернул идентификатор авторизации"
                    )
                }

                sessionId = newSessionId
                authStatus = json.optString("status", "pending")
            } catch (error: Exception) {
                authStatus = "idle"
                errorMessage = error.message
                    ?: "Не удалось отправить запрос авторизации"
            } finally {
                loading = false
            }
        }
    }

    LaunchedEffect(authStatus, sessionId, code) {
        if (
            authStatus == "checking" &&
            sessionId != null &&
            code.length >= 4
        ) {
            try {
                loading = true

                ApiClient.verifyPassengerAuth(
                    sessionId = sessionId!!,
                    code = code
                )
            } catch (error: Exception) {
                authStatus = "otp_required"
                errorMessage = error.message
                    ?: "Не удалось проверить код"
            } finally {
                loading = false
            }
        }
    }
}
