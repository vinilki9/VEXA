
package ru.vexa.driver

import android.content.Context
import android.content.Intent
import android.widget.Toast
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.BackHandler
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import java.io.IOException
import java.text.NumberFormat
import java.util.Locale
import java.text.SimpleDateFormat
import java.util.TimeZone
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

private val VexaTeal = VexaDesign.mutedTeal
private val VexaInk = VexaDesign.graphite
private val VexaNavy = VexaDesign.surfaceDark
private val VexaBackground = VexaDesign.lightCanvas
private val VexaMuted = VexaDesign.lightScheme().onSurfaceVariant
private val VexaRed = Color(0xFFD5444D)

private fun formatWalletRubles(kopecks: Long): String {
 val formatter = NumberFormat.getNumberInstance(Locale("ru", "RU"))
 formatter.minimumFractionDigits = 2
 formatter.maximumFractionDigits = 2
 val sign = if (kopecks < 0) "−" else ""
 return sign + formatter.format(kotlin.math.abs(kopecks) / 100.0)
}

private val apiExecutor = Executors.newSingleThreadExecutor()
private val offerPollExecutor = Executors.newSingleThreadExecutor()
private val offerPollInFlight = AtomicBoolean(false)
private val mainHandler = Handler(Looper.getMainLooper())

private fun parseServerTimestampMillis(value: String): Long? {
 val match = Regex(
  """^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})$"""
 ).matchEntire(value.trim()) ?: return null

 val fraction = (match.groupValues[2] + "000").take(3)
 val normalized = "${match.groupValues[1]}.$fraction${match.groupValues[3]}"

 return try {
  val formatter = SimpleDateFormat(
   "yyyy-MM-dd'T'HH:mm:ss.SSSXXX",
   Locale.US
  )
  formatter.isLenient = false
  formatter.timeZone = TimeZone.getTimeZone("UTC")
  formatter.parse(normalized)?.time
 } catch (_: Exception) {
  null
 }
}

class MainActivity : ComponentActivity() {
 override fun onCreate(savedInstanceState: Bundle?) {
  super.onCreate(savedInstanceState)
  setContent {
   // Login screens and authenticated screens share the same graphite VEXA palette.
   val preferences = remember { DriverPreferences.load(this@MainActivity) }
   val systemDark = isSystemInDarkTheme()
   val dark = preferences.theme == "dark" || (preferences.theme == "system" && systemDark)
   MaterialTheme(colorScheme = if (dark) VexaDesign.darkScheme() else VexaDesign.lightScheme()) {
    DriverScreen()
   }
  }
 }
}

private fun runApiCall(
 action: () -> Any?,
 onResult: (Any?, String?) -> Unit
) {
 apiExecutor.execute {
  try {
   val result = action()
   mainHandler.post {
    onResult(result, null)
   }
  } catch (e: Exception) {
   mainHandler.post {
    onResult(null, e.message ?: "Ошибка соединения с сервером")
   }
  }
 }
}

@Composable
private fun VexaCard(
 dark: Boolean,
 modifier: Modifier = Modifier,
 content: @Composable ColumnScope.() -> Unit
) {
 Card(
  modifier = modifier.fillMaxWidth(),
  shape = RoundedCornerShape(22.dp),
  colors = CardDefaults.cardColors(
   containerColor = if (dark) VexaNavy else Color.White
  ),
  elevation = CardDefaults.cardElevation(
   defaultElevation = if (dark) 0.dp else 2.dp
  )
 ) {
  Column(
   modifier = Modifier.padding(16.dp),
   verticalArrangement = Arrangement.spacedBy(10.dp),
   content = content
  )
 }
}

@Composable
private fun SectionTitle(
 title: String,
 subtitle: String? = null,
 color: Color
) {
 Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
  Text(
   text = title,
   color = color,
   fontSize = 19.sp,
   fontWeight = FontWeight.Bold
  )
  if (!subtitle.isNullOrBlank()) {
   Text(
    text = subtitle,
    color = VexaMuted,
    fontSize = 12.sp
   )
  }
 }
}

@Composable
private fun DriverSatelliteGlyph(color: Color) {
 Canvas(modifier = Modifier.size(24.dp)) {
  val scale = size.width / 24f
  rotate(degrees = 45f, pivot = center) {
   drawRoundRect(
    color = color,
    topLeft = Offset(2f * scale, 9f * scale),
    size = Size(6f * scale, 6f * scale),
    cornerRadius = androidx.compose.ui.geometry.CornerRadius(1f * scale)
   )
   drawRoundRect(
    color = color,
    topLeft = Offset(9f * scale, 9f * scale),
    size = Size(6f * scale, 6f * scale),
    cornerRadius = androidx.compose.ui.geometry.CornerRadius(1f * scale)
   )
   drawRoundRect(
    color = color,
    topLeft = Offset(16f * scale, 9f * scale),
    size = Size(6f * scale, 6f * scale),
    cornerRadius = androidx.compose.ui.geometry.CornerRadius(1f * scale)
   )
  }
  drawLine(
   color = color,
   start = Offset(6f * scale, 6f * scale),
   end = Offset(3f * scale, 3f * scale),
   strokeWidth = 2f * scale,
   cap = androidx.compose.ui.graphics.StrokeCap.Round
  )
  drawLine(
   color = color,
   start = Offset(18f * scale, 18f * scale),
   end = Offset(21f * scale, 21f * scale),
   strokeWidth = 2f * scale,
   cap = androidx.compose.ui.graphics.StrokeCap.Round
  )
 }
}

@Composable
private fun DriverKeyGlyph(color: Color) {
 Canvas(modifier = Modifier.size(24.dp)) {
  val scale = size.width / 24f
  drawCircle(
   color = color,
   radius = 4.2f * scale,
   center = Offset(7.5f * scale, 7.5f * scale),
   style = Stroke(width = 2.5f * scale)
  )
  drawLine(
   color = color,
   start = Offset(10.5f * scale, 10.5f * scale),
   end = Offset(20.5f * scale, 20.5f * scale),
   strokeWidth = 2.5f * scale,
   cap = androidx.compose.ui.graphics.StrokeCap.Round
  )
  drawLine(
   color = color,
   start = Offset(15.5f * scale, 15.5f * scale),
   end = Offset(18f * scale, 13f * scale),
   strokeWidth = 2.5f * scale,
   cap = androidx.compose.ui.graphics.StrokeCap.Round
  )
  drawLine(
   color = color,
   start = Offset(18f * scale, 18f * scale),
   end = Offset(20.5f * scale, 15.5f * scale),
   strokeWidth = 2.5f * scale,
   cap = androidx.compose.ui.graphics.StrokeCap.Round
  )
 }
}

@Composable
private fun DriverSignalGlyph(color: Color) {
 Column(
  horizontalAlignment = Alignment.CenterHorizontally,
  verticalArrangement = Arrangement.spacedBy(2.dp),
  modifier = Modifier.width(26.dp)
 ) {
  listOf(24.dp, 18.dp, 12.dp, 6.dp).forEach { barWidth ->
   Box(
    modifier = Modifier
     .width(barWidth)
     .height(3.dp)
     .background(color, RoundedCornerShape(50))
   )
  }
  Box(
   modifier = Modifier
    .size(4.dp)
    .background(color, RoundedCornerShape(50))
  )
 }
}

@Composable
fun DriverScreen() {
 val context = androidx.compose.ui.platform.LocalContext.current
 var login by remember { mutableStateOf("") }
 var password by remember { mutableStateOf("") }

 var authorized by remember {
  mutableStateOf(DriverApiClient.getAccessToken() != null)
 }

 var initialSessionRestorePending by remember {
  mutableStateOf(DriverApiClient.getAccessToken() != null)
 }

 var loading by remember { mutableStateOf(false) }
 var online by remember { mutableStateOf(false) }
 // Visual break mode is session-local; the server's is_online flag is authoritative.
 var onBreak by remember { mutableStateOf(false) }

 var driverName by remember { mutableStateOf("Водитель") }
 var phone by remember { mutableStateOf("") }
 var cityName by remember { mutableStateOf("Оболенск") }
 var branchName by remember { mutableStateOf("") }
 var rating by remember { mutableStateOf("") }
 var vehicleDescription by remember { mutableStateOf("") }

 var orders by remember { mutableStateOf(listOf<JSONObject>()) }
 var currentOffer by remember { mutableStateOf<JSONObject?>(null) }
 var offerDeadlineMillis by remember { mutableStateOf(0L) }
 var offerSecondsLeft by remember { mutableStateOf(0) }
 var offerActionInProgress by remember { mutableStateOf(false) }
 var lastResolvedOfferId by remember { mutableStateOf("") }
 var offerPollStatusMessage by remember { mutableStateOf("") }
 var walletBalanceKopecks by remember { mutableStateOf<Long?>(null) }
 var walletAvailableKopecks by remember { mutableStateOf<Long?>(null) }

 var gpsHealthy by remember { mutableStateOf(false) }
 var serverHealthy by remember { mutableStateOf(false) }
 var authHealthy by remember { mutableStateOf(false) }
 var selectedStatusDetails by remember {
  mutableStateOf<Pair<String, String>?>(null)
 }

 var errorMessage by remember { mutableStateOf("") }
 var infoMessage by remember { mutableStateOf("") }

 var driverPreferences by remember(context) {
  mutableStateOf(DriverPreferences.load(context))
 }
 var settingsOpen by remember { mutableStateOf(false) }
 BackHandler(enabled = settingsOpen) { settingsOpen = false }
 fun updatePreferences(next: DriverPreferences.State) {
  driverPreferences = next
  DriverPreferences.save(context, next)
 }

 DriverGpsReporter(
  enabled = authorized,
  onMessage = { message ->
   infoMessage = message
  }
 )

 LaunchedEffect(context, authorized) {
  val healthPrefs = context.getSharedPreferences(
   DriverLocationService.STATUS_PREFS,
   Context.MODE_PRIVATE
  )
  var lastAlertId = healthPrefs.getLong(
   DriverLocationService.KEY_ALERT_ID,
   0L
  )

  while (true) {
   gpsHealthy = authorized && healthPrefs.getBoolean(
    DriverLocationService.KEY_GPS_OK,
    false
   )
   serverHealthy = authorized && healthPrefs.getBoolean(
    DriverLocationService.KEY_SERVER_OK,
    false
   )
   authHealthy = authorized && healthPrefs.getBoolean(
    DriverLocationService.KEY_AUTH_OK,
    false
   )

   val currentAlertId = healthPrefs.getLong(
    DriverLocationService.KEY_ALERT_ID,
    0L
   )
   if (currentAlertId != lastAlertId) {
    lastAlertId = currentAlertId
    val alert = healthPrefs.getString(
     DriverLocationService.KEY_ALERT,
     ""
    ).orEmpty()
    if (alert.isNotBlank()) {
     Toast.makeText(context, alert, Toast.LENGTH_SHORT).show()
    }
   }

   kotlinx.coroutines.delay(1000)
  }
 }

 LaunchedEffect(authorized, online) {
  if (!authorized || !online) {
   currentOffer = null
   offerDeadlineMillis = 0L
   offerSecondsLeft = 0
   offerActionInProgress = false
   offerPollStatusMessage = ""
  } else {
   while (true) {
    if (
     !offerActionInProgress &&
     offerPollInFlight.compareAndSet(false, true)
    ) {
     offerPollExecutor.execute {
      try {
       val response = DriverApiClient.getOrderOffers()
       val offers = response.optJSONArray("offers")
       val firstOffer = if (offers != null && offers.length() > 0) {
        offers.optJSONObject(0)
       } else {
        null
       }

       mainHandler.post {
        offerPollInFlight.set(false)

        if (authorized && online && !offerActionInProgress) {
         offerPollStatusMessage = ""

         if (firstOffer == null) {
          currentOffer = null
          offerDeadlineMillis = 0L
          offerSecondsLeft = 0
         } else {
          val offerId = firstOffer.optString("offer_id")
          if (offerId.isNotBlank() && offerId != lastResolvedOfferId) {
           val currentId = currentOffer?.optString("offer_id").orEmpty()
           if (currentId != offerId) {
            currentOffer = firstOffer
            val timeoutSeconds = firstOffer.optInt(
             "response_timeout_seconds",
             13
            ).coerceAtLeast(1)
            val serverDeadline = parseServerTimestampMillis(
             firstOffer.optString("expires_at")
            )
            offerDeadlineMillis = serverDeadline
             ?: (System.currentTimeMillis() +
                 (timeoutSeconds - 2).coerceAtLeast(1) * 1000L)
           } else {
            currentOffer = firstOffer
           }
          }
         }
        }
       }
      } catch (e: Exception) {
       val statusMessage = when (e) {
        is DriverApiHttpException -> when {
         e.statusCode == 401 || e.statusCode == 403 ->
          "Ошибка авторизации (HTTP ${e.statusCode}). Проверьте вход в аккаунт водителя."
         e.statusCode in 500..599 ->
          "Сервер временно недоступен (HTTP ${e.statusCode}). VEXA продолжит проверку автоматически."
         else ->
          "Сервер вернул ошибку HTTP ${e.statusCode}: ${e.message.orEmpty()}"
        }
        is IOException ->
         "Нет связи с сервером. VEXA автоматически возобновит получение заказов после восстановления интернета."
        else ->
         "Не удалось получить предложения заказов: ${e.message ?: "неизвестная ошибка"}"
       }
       mainHandler.post {
        offerPollInFlight.set(false)
        if (authorized && online) {
         offerPollStatusMessage = statusMessage
        }
       }
      }
     }
    }

    kotlinx.coroutines.delay(2000)
   }
  }
 }

 LaunchedEffect(currentOffer?.optString("offer_id"), offerDeadlineMillis) {
  while (currentOffer != null && offerDeadlineMillis > 0L) {
   val remainingMillis = offerDeadlineMillis - System.currentTimeMillis()
   if (remainingMillis <= 0L) {
    currentOffer?.let {
     lastResolvedOfferId = it.optString("offer_id")
    }
    currentOffer = null
    offerSecondsLeft = 0
    break
   }

   offerSecondsLeft = ((remainingMillis + 999L) / 1000L)
    .toInt()
    .coerceAtLeast(1)
   kotlinx.coroutines.delay(250)
  }
 }

 val systemDark = isSystemInDarkTheme()
 val dark = driverPreferences.theme == "dark" ||
         (driverPreferences.theme == "system" && systemDark)

 val backgroundColor = if (dark) VexaDesign.graphite else VexaDesign.lightCanvas
 val foregroundColor = if (dark) VexaDesign.textDark else VexaDesign.textLight
 val secondaryText = if (dark) VexaDesign.darkScheme().onSurfaceVariant else VexaDesign.lightScheme().onSurfaceVariant
 val cardColor = if (dark) VexaDesign.surfaceDark else VexaDesign.lightSurface

 fun loadDriverData() {
  loading = true
  errorMessage = ""

  runApiCall(
   action = {
    val profile = DriverApiClient.getProfile()
    val activeOrders = DriverApiClient.getActiveOrders()
    val wallet = DriverApiClient.getWallet()
    Triple(profile, activeOrders, wallet)
   },
   onResult = { result, error ->
    loading = false

    if (error != null) {
     errorMessage = error
     return@runApiCall
    }

    val data = result as Triple<*, *, *>
    val profile = data.first as JSONObject
    val activeOrders = data.second as JSONObject
    val wallet = data.third as JSONObject

    walletBalanceKopecks = wallet.optLong("balance_kopecks", 0L)
    walletAvailableKopecks = wallet.optLong("available_kopecks", 0L)

    driverName = profile.optString("username", "Водитель")
    phone = profile.optString("phone", "")
    online = profile.optBoolean("is_online", false)
    if (online) onBreak = false
    rating = profile.optString("rating", "")

    cityName = profile
     .optJSONObject("city")
     ?.optString("name", "Оболенск")
     ?: "Оболенск"

    branchName = profile
     .optJSONObject("branch")
     ?.optString("name", "")
     ?: ""

    val vehicles = profile.optJSONArray("vehicles")
    vehicleDescription = if (
     vehicles != null && vehicles.length() > 0
    ) {
     val vehicle = vehicles.getJSONObject(0)
     listOf(
      vehicle.optString("make"),
      vehicle.optString("model"),
      vehicle.optString("color"),
      vehicle.optString("license_plate")
     )
      .filter { it.isNotBlank() && it != "null" }
      .joinToString(" · ")
    } else {
     "Автомобиль не указан"
    }

    val orderArray = activeOrders.optJSONArray("orders")
    val loadedOrders = mutableListOf<JSONObject>()

    if (orderArray != null) {
     for (i in 0 until orderArray.length()) {
      loadedOrders.add(orderArray.getJSONObject(i))
     }
    }

    orders = loadedOrders
    authorized = true
    infoMessage = "Данные водителя обновлены"
   }
  )
 }

 LaunchedEffect(initialSessionRestorePending) {
  if (initialSessionRestorePending) {
   initialSessionRestorePending = false
   loadDriverData()
  }
 }

 fun changeOnlineStatus(value: Boolean, startBreak: Boolean = false) {
  if (loading) return

  loading = true
  errorMessage = ""

  runApiCall(
   action = {
    DriverApiClient.setOnline(value)
   },
   onResult = { result, error ->
    loading = false

    if (error != null) {
     errorMessage = error
     return@runApiCall
    }

    val response = result as JSONObject
    online = response.optBoolean("is_online", value)
    onBreak = !online && startBreak
    if (!online) DriverLocationService.stop(context)

    infoMessage = if (onBreak) {
     "Перерыв. Новые заказы не предлагаются"
    } else if (online) {
     "Вы вышли на линию"
    } else {
     "Вы сняты с линии"
    }

    if (online) {
     loadDriverData()
    }
   }
  )
 }

 fun refreshOrders(announce: Boolean = true) {
  if (loading) return

  loading = true
  errorMessage = ""

  runApiCall(
   action = {
    DriverApiClient.getActiveOrders()
   },
   onResult = { result, error ->
    loading = false

    if (error != null) {
     errorMessage = error
     return@runApiCall
    }

    val response = result as JSONObject
    val array = response.optJSONArray("orders")
    val updated = mutableListOf<JSONObject>()

    if (array != null) {
     for (i in 0 until array.length()) {
      updated.add(array.getJSONObject(i))
     }
    }

    orders = updated
    if (announce) infoMessage = "Список заказов обновлён"
   }
  )
 }

 fun respondToOffer(accept: Boolean) {
  val offer = currentOffer ?: return
  if (offerActionInProgress) return

  val offerId = offer.optString("offer_id")
  if (offerId.isBlank()) {
   errorMessage = "Не удалось определить предложение заказа"
   return
  }

  offerActionInProgress = true
  errorMessage = ""

  runApiCall(
   action = {
    if (accept) {
     DriverApiClient.acceptOrderOffer(offerId)
    } else {
     DriverApiClient.rejectOrderOffer(offerId)
    }
   },
   onResult = { result, error ->
    offerActionInProgress = false

    if (error != null) {
     errorMessage = error
     return@runApiCall
    }

    val response = result as JSONObject
    val failed = !response.optBoolean("success", true) ||
     response.optBoolean("expired", false) ||
     response.optBoolean("cancelled", false)

    if (failed) {
     lastResolvedOfferId = offerId
     currentOffer = null
     offerDeadlineMillis = 0L
     offerSecondsLeft = 0
     infoMessage = response.optString(
      "message",
      "Предложение больше недоступно"
     )
    } else {
     lastResolvedOfferId = offerId
     currentOffer = null
     offerDeadlineMillis = 0L
     offerSecondsLeft = 0

     if (accept) {
      infoMessage = "Заказ принят. Загружаем карточку поездки"
      refreshOrders()
     } else {
      infoMessage = "Вы отказались от заказа"
     }
    }
   }
  )
 }

 fun advanceOrder(order: JSONObject) {
  if (loading) return

  val orderId = order.optString("id")
  val currentStatus = order.optString("status")

  val nextStatus = when (currentStatus) {
   "assigned" -> "arrived"
   "arrived" -> "in_progress"
   "in_progress" -> "completed"
   else -> return
  }

  loading = true
  errorMessage = ""

  runApiCall(
   action = {
    val response = DriverApiClient.updateOrderStatus(
     orderId = orderId,
     status = nextStatus
    )
    val wallet = if (nextStatus == "completed") {
     runCatching { DriverApiClient.getWallet() }.getOrNull()
    } else {
     null
    }
    Pair(response, wallet)
   },
   onResult = { result, error ->
    loading = false

    if (error != null) {
     errorMessage = error
     // Статус мог сохраниться на сервере, даже если ответ потерялся.
     refreshOrders(announce = false)
    } else {
     val data = result as Pair<*, *>
     val wallet = data.second as? JSONObject
     if (wallet != null) {
      walletBalanceKopecks = wallet.optLong("balance_kopecks", 0L)
      walletAvailableKopecks = wallet.optLong("available_kopecks", 0L)
     }
     infoMessage = when {
      nextStatus == "completed" && wallet == null ->
       "Поездка завершена. Баланс обновится после восстановления связи"
      nextStatus == "completed" -> "Поездка завершена. Баланс обновлён"
      else -> "Статус заказа обновлён"
     }
     refreshOrders(announce = false)
    }
   }
  )
 }

 MaterialTheme(
  colorScheme = if (dark) VexaDesign.darkScheme() else VexaDesign.lightScheme()
 ) {
  Surface(
   modifier = Modifier.fillMaxSize(),
   color = backgroundColor
  ) {
   if (!authorized) {
    Column(
     modifier = Modifier
      .fillMaxSize()
      .background(backgroundColor)
      .padding(24.dp),
     horizontalAlignment = Alignment.CenterHorizontally,
     verticalArrangement = Arrangement.Center
    ) {
     Text(
      text = "VEXA",
      color = VexaTeal,
      fontSize = 42.sp,
      fontWeight = FontWeight.ExtraBold,
      letterSpacing = 3.sp
     )

     Text(
      text = "ВОДИТЕЛЬ",
      color = foregroundColor,
      fontSize = 13.sp,
      fontWeight = FontWeight.Bold,
      letterSpacing = 4.sp
     )

     Spacer(Modifier.height(30.dp))

     VexaCard(dark = dark) {
      SectionTitle(
       title = "Вход в аккаунт",
       subtitle = "Введите данные учётной записи водителя",
       color = foregroundColor
      )

      OutlinedTextField(
       value = login,
       onValueChange = { login = it },
       modifier = Modifier.fillMaxWidth(),
       label = { Text("Логин или телефон") },
       singleLine = true,
       enabled = !loading,
       shape = RoundedCornerShape(14.dp)
      )

      OutlinedTextField(
       value = password,
       onValueChange = { password = it },
       modifier = Modifier.fillMaxWidth(),
       label = { Text("Пароль") },
       singleLine = true,
       enabled = !loading,
       visualTransformation = PasswordVisualTransformation(),
       keyboardOptions = KeyboardOptions(
        keyboardType = KeyboardType.Password
       ),
       shape = RoundedCornerShape(14.dp)
      )

      if (errorMessage.isNotBlank()) {
       Text(
        text = errorMessage,
        color = MaterialTheme.colorScheme.error,
        fontSize = 12.sp
       )
      }

      Button(
       onClick = {
        if (login.isBlank() || password.isBlank()) {
         errorMessage = "Введите логин и пароль"
         return@Button
        }

        loading = true
        errorMessage = ""

        runApiCall(
         action = {
          DriverApiClient.login(
           login.trim(),
           password
          )
          DriverApiClient.getProfile()
          DriverApiClient.getActiveOrders()
         },
         onResult = { _, error ->
          loading = false

          if (error != null) {
           DriverApiClient.clearAccessToken()
           errorMessage = error
          } else {
           password = ""
           loadDriverData()
          }
         }
        )
       },
       modifier = Modifier
        .fillMaxWidth()
        .height(52.dp),
       enabled = !loading,
       shape = RoundedCornerShape(15.dp),
       colors = ButtonDefaults.buttonColors(
        containerColor = VexaTeal,
        contentColor = VexaInk
       )
      ) {
       Text(
        text = if (loading) "Подключение..." else "ВОЙТИ",
        fontWeight = FontWeight.Bold
       )
      }

      Text(
       text = "Сервер VEXA · локальный компьютер",
       color = VexaMuted,
       fontSize = 11.sp
      )
     }
    }
   } else if (settingsOpen) {
    DriverSettingsScreen(
     value = driverPreferences,
     onValueChange = ::updatePreferences,
     onBack = { settingsOpen = false },
     onLogout = {
      DriverApiClient.clearAccessToken()
      DriverLocationService.stop(context)
      authorized = false
      online = false
      onBreak = false
      orders = emptyList()
      settingsOpen = false
      errorMessage = ""
      infoMessage = "Вы вышли из профиля"
     },
     driverName = driverName,
     phone = phone,
     cityName = cityName,
     vehicleDescription = vehicleDescription
    )
   } else {
    LazyColumn(
     modifier = Modifier
      .fillMaxSize()
      .padding(horizontal = 16.dp),
     verticalArrangement = Arrangement.spacedBy(14.dp),
     contentPadding = PaddingValues(
      top = 16.dp,
      bottom = 30.dp
     )
    ) {
     item {
      Row(
       modifier = Modifier.fillMaxWidth(),
       horizontalArrangement = Arrangement.spacedBy(4.dp),
       verticalAlignment = Alignment.CenterVertically
      ) {
       IconButton(
        onClick = {
         selectedStatusDetails = Pair(
          "GPS",
          when {
           gpsHealthy -> "GPS работает. Последние координаты успешно передаются серверу VEXA."
           !online -> "Водитель не на линии. Передача координат остановлена."
           else -> "GPS недоступен или передача координат не подтверждена. Проверьте разрешение на местоположение и настройки геолокации."
          }
         )
        },
        modifier = Modifier.size(40.dp)
       ) {
        DriverSatelliteGlyph(
         color = if (gpsHealthy) VexaTeal else VexaRed
        )
       }

       IconButton(
        onClick = {
         selectedStatusDetails = Pair(
          "Связь с сервером",
          if (serverHealthy) {
           "Соединение с сервером VEXA подтверждено."
          } else {
           "Нет подтверждённого соединения с сервером VEXA. Приложение продолжит проверять связь автоматически."
          }
         )
        },
        modifier = Modifier.size(40.dp)
       ) {
        DriverSignalGlyph(
         color = if (serverHealthy) VexaTeal else VexaRed
        )
       }

       IconButton(
        onClick = {
         selectedStatusDetails = Pair(
          "Авторизация",
          if (authHealthy) {
           "Авторизация водителя подтверждена сервером VEXA."
          } else {
           "Авторизация не подтверждена. Проверьте вход в профиль водителя."
          }
         )
        },
        modifier = Modifier.size(40.dp)
       ) {
        DriverKeyGlyph(
         color = if (authHealthy) VexaTeal else VexaRed
        )
       }
      }
     }

     item {
      Row(
       modifier = Modifier
        .fillMaxWidth()
        .padding(vertical = 4.dp),
       verticalAlignment = Alignment.CenterVertically
      ) {
       Column {
        Text(
         text = "VEXA",
         color = VexaTeal,
         fontSize = 27.sp,
         fontWeight = FontWeight.ExtraBold,
         letterSpacing = 2.sp
        )
        Text(
         text = "ВОДИТЕЛЬ",
         color = secondaryText,
         fontSize = 10.sp,
         fontWeight = FontWeight.Bold,
         letterSpacing = 3.sp
        )
       }

       Spacer(Modifier.weight(1f))

       Surface(
        color = if (online) {
         VexaTeal.copy(alpha = 0.16f)
        } else {
         Color.Gray.copy(alpha = 0.14f)
        },
        shape = RoundedCornerShape(50)
       ) {
        Text(
         text = if (online) "● НА ЛИНИИ" else "● НЕ НА ЛИНИИ",
         modifier = Modifier.padding(
          horizontal = 12.dp,
          vertical = 8.dp
         ),
         color = if (online) VexaTeal else secondaryText,
         fontSize = 10.sp,
         fontWeight = FontWeight.Bold
        )
       }

       IconButton(onClick = { settingsOpen = true }) {
        Icon(Icons.Default.MoreVert, contentDescription = "Настройки VEXA Driver", tint = foregroundColor)
       }
      }
     }

     if (currentOffer != null && online) {
      item {
       val offer = currentOffer!!
       val order = offer.optJSONObject("order") ?: JSONObject()
       val pickup = order.optJSONObject("pickup")
        ?.optString("address", "Не указан")
        ?: "Не указан"
       val destination = order.optJSONObject("destination")
        ?.optString("address", "Не указан")
        ?: "Не указан"
       val orderNumber = order.optString(
        "public_number",
        order.optString("id", "—")
       )
       val price = order.optString("price_rub", "")
       val distanceMeters = offer.optInt("distance_to_pickup_meters", -1)
       val distanceText = when {
        distanceMeters < 0 -> ""
        distanceMeters >= 1000 -> String.format(
         Locale("ru", "RU"),
         "%.1f км",
         distanceMeters / 1000.0
        )
        else -> "$distanceMeters м"
       }

       VexaCard(dark = dark) {
        Row(
         modifier = Modifier.fillMaxWidth(),
         verticalAlignment = Alignment.CenterVertically
        ) {
         Column(modifier = Modifier.weight(1f)) {
          Text(
           text = "НОВОЕ ПРЕДЛОЖЕНИЕ",
           color = VexaTeal,
           fontSize = 12.sp,
           fontWeight = FontWeight.ExtraBold,
           letterSpacing = 1.sp
          )
          Text(
           text = "Заказ № $orderNumber",
           color = foregroundColor,
           fontSize = 18.sp,
           fontWeight = FontWeight.Bold
          )
         }
         Surface(
          color = if (offerSecondsLeft <= 5) {
           MaterialTheme.colorScheme.errorContainer
          } else {
           VexaTeal.copy(alpha = 0.16f)
          },
          shape = RoundedCornerShape(14.dp)
         ) {
          Text(
           text = "$offerSecondsLeft сек.",
           modifier = Modifier.padding(
            horizontal = 12.dp,
            vertical = 9.dp
           ),
           color = if (offerSecondsLeft <= 5) {
            MaterialTheme.colorScheme.onErrorContainer
           } else {
            if (dark) VexaTeal else Color(0xFF087F75)
           },
           fontSize = 16.sp,
           fontWeight = FontWeight.ExtraBold
          )
         }
        }

        HorizontalDivider(
         color = if (dark) Color.White.copy(alpha = 0.08f)
         else Color.Black.copy(alpha = 0.06f)
        )

        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
         Text(
          text = "ОТКУДА",
          color = VexaMuted,
          fontSize = 9.sp,
          fontWeight = FontWeight.Bold
         )
         Text(
          text = pickup,
          color = foregroundColor,
          fontSize = 14.sp,
          fontWeight = FontWeight.Medium
         )
        }

        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
         Text(
          text = "КУДА",
          color = VexaMuted,
          fontSize = 9.sp,
          fontWeight = FontWeight.Bold
         )
         Text(
          text = destination,
          color = foregroundColor,
          fontSize = 14.sp,
          fontWeight = FontWeight.Medium
         )
        }

        Row(
         modifier = Modifier.fillMaxWidth(),
         verticalAlignment = Alignment.CenterVertically
        ) {
         if (price.isNotBlank() && price != "null") {
          Text(
           text = "Стоимость: $price ₽",
           color = foregroundColor,
           fontSize = 17.sp,
           fontWeight = FontWeight.Bold
          )
         }
         Spacer(Modifier.weight(1f))
         if (distanceText.isNotBlank()) {
          Text(
           text = "До подачи: $distanceText",
           color = secondaryText,
           fontSize = 11.sp
          )
         }
        }

        Text(
         text = "Ответьте до окончания таймера. Если не успеть, предложение автоматически перейдёт следующему водителю.",
         color = secondaryText,
         fontSize = 11.sp
        )

        Row(
         modifier = Modifier.fillMaxWidth(),
         horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
         OutlinedButton(
          onClick = { respondToOffer(false) },
          enabled = !offerActionInProgress && offerSecondsLeft > 0,
          modifier = Modifier.weight(1f).height(50.dp),
          shape = RoundedCornerShape(14.dp)
         ) {
          Text("ОТКЛОНИТЬ")
         }

         Button(
          onClick = { respondToOffer(true) },
          enabled = !offerActionInProgress && offerSecondsLeft > 0,
          modifier = Modifier.weight(1f).height(50.dp),
          shape = RoundedCornerShape(14.dp),
          colors = ButtonDefaults.buttonColors(
           containerColor = VexaTeal,
           contentColor = VexaInk
          )
         ) {
          Text(
           text = if (offerActionInProgress) "ОТПРАВКА..." else "ПРИНЯТЬ",
           fontWeight = FontWeight.Bold
          )
         }
        }
       }
      }
     }

     item {
      DriverHomeMapCard(
       cityName = cityName,
       followGps = driverPreferences.followGps,
       activeOrder = orders.firstOrNull { order ->
        order.optString("status") in setOf("assigned", "arrived", "in_progress")
       }
      )
     }

     item {
      VexaCard(dark = dark) {
       Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
       ) {
        Column(
         modifier = Modifier.weight(1f),
         verticalArrangement = Arrangement.spacedBy(5.dp)
        ) {
         Text(
          text = driverName,
          color = foregroundColor,
          fontSize = 21.sp,
          fontWeight = FontWeight.Bold
         )

         if (phone.isNotBlank()) {
          Text(
           text = phone,
           color = secondaryText,
           fontSize = 13.sp
          )
         }

         Text(
          text = "Город: $cityName",
          color = secondaryText,
          fontSize = 12.sp
         )

         if (branchName.isNotBlank()) {
          Text(
           text = "Филиал: $branchName",
           color = secondaryText,
           fontSize = 12.sp
          )
         }
        }

        if (rating.isNotBlank()) {
         Surface(
          color = VexaTeal.copy(alpha = 0.14f),
          shape = RoundedCornerShape(16.dp)
         ) {
          Column(
           modifier = Modifier.padding(
            horizontal = 14.dp,
            vertical = 10.dp
           ),
           horizontalAlignment = Alignment.CenterHorizontally
          ) {
           Text(
            text = "★",
            color = VexaTeal,
            fontSize = 19.sp
           )
           Text(
            text = rating,
            color = foregroundColor,
            fontWeight = FontWeight.Bold,
            fontSize = 14.sp
           )
           Text(
            text = "РЕЙТИНГ",
            color = secondaryText,
            fontSize = 8.sp
           )
          }
         }
        }
       }

       HorizontalDivider(
        color = if (dark) Color.White.copy(alpha = 0.08f)
        else Color.Black.copy(alpha = 0.06f)
       )

       Text(
        text = vehicleDescription,
        color = foregroundColor,
        fontSize = 13.sp,
        fontWeight = FontWeight.Medium
       )
      }
     }

     item {
      VexaCard(dark = dark) {
       Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(6.dp)
       ) {
        Text(
         text = "ТЕКУЩИЙ БАЛАНС",
         color = secondaryText,
         fontSize = 11.sp,
         fontWeight = FontWeight.Bold,
         letterSpacing = 1.sp
        )
        Text(
         text = walletBalanceKopecks?.let { "${formatWalletRubles(it)} ₽" } ?: "—",
         color = if (dark) VexaTeal else Color(0xFF087F75),
         fontSize = 32.sp,
         fontWeight = FontWeight.ExtraBold
        )
        Text(
         text = walletAvailableKopecks?.let {
          "Доступно к выводу: ${formatWalletRubles(it)} ₽"
         } ?: "Доступно к выводу: —",
         color = secondaryText,
         fontSize = 12.sp
        )
       }
      }
     }

     item {
      VexaCard(dark = dark) {
       Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
       ) {
        Column(
         modifier = Modifier.weight(1f),
         verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
         Text(
          text = "Финансы",
          color = foregroundColor,
          fontSize = 17.sp,
          fontWeight = FontWeight.Bold
         )
         Text(
          text = "Баланс, заработок, комиссия и история операций",
          color = secondaryText,
          fontSize = 11.sp
         )
        }

        Button(
         onClick = {
          context.startActivity(
           Intent(context, DriverFinanceActivity::class.java)
          )
         },
         modifier = Modifier.height(48.dp),
         shape = RoundedCornerShape(14.dp),
         colors = ButtonDefaults.buttonColors(
          containerColor = VexaTeal,
          contentColor = VexaInk
         )
        ) {
         Text(
          text = "ДЕНЬГИ",
          fontSize = 13.sp,
          fontWeight = FontWeight.ExtraBold,
          letterSpacing = 0.6.sp
         )
        }
       }
      }
     }

     item {
      VexaCard(dark = dark) {
       val canBreak = DriverDutyRules.canStartBreak(
        orders.map { it.optString("status") }, currentOffer != null
       )
       Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
       ) {
        Column(
         modifier = Modifier.weight(1f),
         verticalArrangement = Arrangement.spacedBy(5.dp)
        ) {
         Text(
          text = if (online) "Вы на линии" else "Вы не на линии",
          color = foregroundColor,
          fontSize = 18.sp,
          fontWeight = FontWeight.Bold
         )

         Text(
          text = if (online) {
           "Вы доступны для получения заказов"
          } else {
           "Включите режим, чтобы получать заказы"
          },
          color = secondaryText,
          fontSize = 11.sp
         )
        }

        Switch(
         checked = online,
         onCheckedChange = { changeOnlineStatus(it) },
         enabled = !loading && (!online || canBreak),
         colors = SwitchDefaults.colors(
          checkedThumbColor = Color.White,
          checkedTrackColor = VexaTeal,
          uncheckedThumbColor = Color.White,
          uncheckedTrackColor = Color.Gray
         )
        )
       }
        if (online || onBreak) {
         OutlinedButton(
          onClick = {
           if (onBreak) changeOnlineStatus(true)
           else if (canBreak) changeOnlineStatus(false, startBreak = true)
          },
          enabled = !loading && (onBreak || canBreak),
          modifier = Modifier.fillMaxWidth()
         ) { Text(if (onBreak) "Вернуться на линию" else "Перерыв") }
         if (online && !canBreak) {
          Text("Перерыв недоступен во время заказа или активного предложения",
           color = secondaryText, fontSize = 11.sp)
         }
        }
      }
     }

     if (offerPollStatusMessage.isNotBlank() && online) {
      item {
       Surface(
        modifier = Modifier.fillMaxWidth(),
        color = MaterialTheme.colorScheme.errorContainer,
        shape = RoundedCornerShape(14.dp)
       ) {
        Text(
         text = offerPollStatusMessage,
         modifier = Modifier.padding(12.dp),
         color = MaterialTheme.colorScheme.onErrorContainer,
         fontSize = 12.sp
        )
       }
      }
     }

     item {
      Row(
       modifier = Modifier.fillMaxWidth(),
       verticalAlignment = Alignment.CenterVertically
      ) {
       Column {
        Text(
         text = "Активные заказы",
         color = foregroundColor,
         fontSize = 20.sp,
         fontWeight = FontWeight.Bold
        )
        Text(
         text = "Ваши текущие поездки",
         color = secondaryText,
         fontSize = 11.sp
        )
       }

       Spacer(Modifier.weight(1f))

       TextButton(
        onClick = { refreshOrders() },
        enabled = !loading
       ) {
        Text("Обновить", color = VexaTeal)
       }
      }
     }

     if (orders.isEmpty()) {
      item {
       VexaCard(dark = dark) {
        Box(
         modifier = Modifier
          .fillMaxWidth()
          .padding(vertical = 20.dp),
         contentAlignment = Alignment.Center
        ) {
         Column(
          horizontalAlignment = Alignment.CenterHorizontally,
          verticalArrangement = Arrangement.spacedBy(8.dp)
         ) {
          Text(
           text = "—",
           color = VexaTeal,
           fontSize = 32.sp,
           fontWeight = FontWeight.Bold
          )
          Text(
           text = "Активных заказов пока нет",
           color = foregroundColor,
           fontWeight = FontWeight.SemiBold
          )
          Text(
           text = "Новые назначения появятся здесь",
           color = secondaryText,
           fontSize = 11.sp
          )
         }
        }
       }
      }
     } else {
      items(
       items = orders,
       key = { it.optString("id") }
      ) { order ->
       val pickup = order
        .optJSONObject("pickup")
        ?.optString("address", "Не указан")
        ?: "Не указан"

       val destination = order
        .optJSONObject("destination")
        ?.optString("address", "Не указан")
        ?: "Не указан"

       val status = order.optString("status")
       val orderNumber = order.optString(
        "public_number",
        order.optString("id")
       )

       val statusText = when (status) {
        "new" -> "Новый заказ"
        "accepted" -> "Принят диспетчером"
        "assigned" -> "Водитель назначен"
        "arrived" -> "Вы на месте"
        "in_progress" -> "Поездка выполняется"
        "completed" -> "Поездка завершена"
        "cancelled" -> "Заказ отменён"
        else -> status
       }

       val nextAction = when (status) {
        "assigned" -> "Я на месте"
        "arrived" -> "Начать поездку"
        "in_progress" -> "Завершить поездку"
        else -> null
       }

       val price = order.optString("price_rub", "")

       VexaCard(dark = dark) {
        Row(
         modifier = Modifier.fillMaxWidth(),
         verticalAlignment = Alignment.CenterVertically
        ) {
         Text(
          text = "ЗАКАЗ № $orderNumber",
          color = VexaTeal,
          fontSize = 13.sp,
          fontWeight = FontWeight.Bold
         )

         Spacer(Modifier.weight(1f))

         Surface(
          color = VexaTeal.copy(alpha = 0.14f),
          shape = RoundedCornerShape(50)
         ) {
          Text(
           text = statusText,
           modifier = Modifier.padding(
            horizontal = 10.dp,
            vertical = 6.dp
           ),
           color = if (dark) VexaTeal else Color(0xFF087F75),
           fontSize = 10.sp,
           fontWeight = FontWeight.SemiBold
          )
         }
        }

        HorizontalDivider(
         color = if (dark) Color.White.copy(alpha = 0.08f)
         else Color.Black.copy(alpha = 0.06f)
        )

        Column(
         verticalArrangement = Arrangement.spacedBy(5.dp)
        ) {
         Text(
          text = "ОТКУДА",
          color = VexaMuted,
          fontSize = 9.sp,
          fontWeight = FontWeight.Bold
         )
         Text(
          text = pickup,
          color = foregroundColor,
          fontSize = 14.sp,
          fontWeight = FontWeight.Medium
         )
         val pickupInstructions = order.optString("comment").trim()
         if (pickupInstructions.isNotBlank()) {
          Text("Ориентир / комментарий: $pickupInstructions",
           color = secondaryText, fontSize = 12.sp)
         }
        }

        Row(
         modifier = Modifier.padding(start = 5.dp),
         verticalAlignment = Alignment.CenterVertically
        ) {
         Box(
          modifier = Modifier
           .width(2.dp)
           .height(18.dp)
           .background(VexaTeal)
         )
         Text(
          text = "  ↓",
          color = VexaTeal,
          fontSize = 12.sp
         )
        }

        Column(
         verticalArrangement = Arrangement.spacedBy(5.dp)
        ) {
         Text(
          text = "КУДА",
          color = VexaMuted,
          fontSize = 9.sp,
          fontWeight = FontWeight.Bold
         )
         Text(
          text = destination,
          color = foregroundColor,
          fontSize = 14.sp,
          fontWeight = FontWeight.Medium
         )
        }

        val pickupPoint = order.optJSONObject("pickup")
        val destinationPoint = order.optJSONObject("destination")
        val passengerPhone = order.optString("customer_phone")
        Row(
         modifier = Modifier.fillMaxWidth(),
         horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
         OutlinedButton(
          onClick = { DriverQuickActions.openNavigator(context, pickupPoint) },
          enabled = DriverQuickActions.validPoint(pickupPoint),
          modifier = Modifier.weight(1f)
         ) { Text("К подаче", fontSize = 12.sp) }
         OutlinedButton(
          onClick = { DriverQuickActions.openNavigator(context, destinationPoint) },
          enabled = DriverQuickActions.validPoint(destinationPoint),
          modifier = Modifier.weight(1f)
         ) { Text("К адресу", fontSize = 12.sp) }
        }
        if (DriverQuickActions.validPhone(passengerPhone)) {
         OutlinedButton(
          onClick = { DriverQuickActions.openDialer(context, passengerPhone) },
          modifier = Modifier.fillMaxWidth()
         ) { Text("Позвонить пассажиру") }
        }
        Text(
         "Навигация откроется во внешнем приложении",
         color = secondaryText,
         fontSize = 10.sp
        )

        if (price.isNotBlank() && price != "null") {
         Row(
          modifier = Modifier.fillMaxWidth(),
          verticalAlignment = Alignment.CenterVertically
         ) {
          Text(
           text = "Стоимость поездки",
           color = secondaryText,
           fontSize = 12.sp
          )
          Spacer(Modifier.weight(1f))
          Text(
           text = "$price ₽",
           color = foregroundColor,
           fontSize = 18.sp,
           fontWeight = FontWeight.Bold
          )
         }
        }

        if (nextAction != null) {
         Button(
          onClick = { advanceOrder(order) },
          enabled = !loading,
          modifier = Modifier
           .fillMaxWidth()
           .height(50.dp),
          shape = RoundedCornerShape(14.dp),
          colors = ButtonDefaults.buttonColors(
           containerColor = VexaTeal,
           contentColor = VexaInk
          )
         ) {
          Text(
           text = nextAction,
           fontWeight = FontWeight.Bold
          )
         }
        }
       }
      }
     }
     if (loading) {
      item {
       LinearProgressIndicator(
        modifier = Modifier
         .fillMaxWidth()
         .height(3.dp),
        color = VexaTeal,
        trackColor = VexaTeal.copy(alpha = 0.15f)
       )
      }
     }

     if (errorMessage.isNotBlank()) {
      item {
       Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        shape = RoundedCornerShape(12.dp)
       ) {
        Text(
         text = errorMessage,
         modifier = Modifier.padding(12.dp),
         color = MaterialTheme.colorScheme.onErrorContainer,
         fontSize = 12.sp
        )
       }
      }
     }

     if (infoMessage.isNotBlank()) {
      item {
       Text(
        text = infoMessage,
        color = VexaTeal,
        fontSize = 11.sp
       )
      }
     }

     item {
      Text(
       text = "VEXA Driver · $cityName",
       modifier = Modifier
        .fillMaxWidth()
        .padding(top = 8.dp),
       color = secondaryText,
       fontSize = 10.sp
      )
     }
    }
   }
   if (selectedStatusDetails != null) {
    val details = selectedStatusDetails!!
    AlertDialog(
     onDismissRequest = { selectedStatusDetails = null },
     title = {
      Text(
       text = details.first,
       fontWeight = FontWeight.Bold
      )
     },
     text = {
      Text(details.second)
     },
     confirmButton = {
      TextButton(
       onClick = { selectedStatusDetails = null }
      ) {
       Text("Понятно")
      }
     }
    )
   }
  }
 }
}

@Composable
private fun ClipMapContainer(
 content: @Composable () -> Unit
) {
 Surface(
  shape = RoundedCornerShape(16.dp),
  color = Color.Transparent
 ) {
  content()
 }
}
