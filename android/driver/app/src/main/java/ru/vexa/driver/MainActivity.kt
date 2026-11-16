package ru.vexa.driver

import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import java.util.concurrent.Executors

private val VexaTeal = Color(0xFF20C6B7)
private val VexaInk = Color(0xFF111827)
private val VexaNavy = Color(0xFF1E293B)
private val VexaBackground = Color(0xFFF5F7FA)
private val VexaMuted = Color(0xFF64748B)

private val apiExecutor = Executors.newSingleThreadExecutor()
private val mainHandler = Handler(Looper.getMainLooper())

class MainActivity : ComponentActivity() {
 override fun onCreate(savedInstanceState: Bundle?) {
  super.onCreate(savedInstanceState)
  setContent {
   DriverScreen()
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
fun DriverScreen() {
 val context = androidx.compose.ui.platform.LocalContext.current
 var login by remember { mutableStateOf("") }
 var password by remember { mutableStateOf("") }

 var authorized by remember {
  mutableStateOf(DriverApiClient.getAccessToken() != null)
 }

 var loading by remember { mutableStateOf(false) }
 var online by remember { mutableStateOf(false) }

 var driverName by remember { mutableStateOf("Водитель") }
 var phone by remember { mutableStateOf("") }
 var cityName by remember { mutableStateOf("Оболенск") }
 var branchName by remember { mutableStateOf("") }
 var rating by remember { mutableStateOf("") }
 var vehicleDescription by remember { mutableStateOf("") }

 var orders by remember { mutableStateOf(listOf<JSONObject>()) }

 var errorMessage by remember { mutableStateOf("") }
 var infoMessage by remember { mutableStateOf("") }

 var theme by remember { mutableStateOf("Системная") }
 var sound by remember { mutableStateOf("classic") }

 DriverGpsReporter(
  enabled = authorized,
  onMessage = { message ->
   infoMessage = message
  }
 )

 val systemDark = isSystemInDarkTheme()
 val dark = theme == "Ночная" ||
         (theme == "Системная" && systemDark)

 val backgroundColor = if (dark) VexaInk else VexaBackground
 val foregroundColor = if (dark) Color.White else VexaInk
 val secondaryText = if (dark) Color(0xFFCBD5E1) else VexaMuted
 val cardColor = if (dark) VexaNavy else Color.White

 fun loadDriverData() {
  loading = true
  errorMessage = ""

  runApiCall(
   action = {
    val profile = DriverApiClient.getProfile()
    val activeOrders = DriverApiClient.getActiveOrders()
    Pair(profile, activeOrders)
   },
   onResult = { result, error ->
    loading = false

    if (error != null) {
     errorMessage = error
     return@runApiCall
    }

    val data = result as Pair<*, *>
    val profile = data.first as JSONObject
    val activeOrders = data.second as JSONObject

    driverName = profile.optString("username", "Водитель")
    phone = profile.optString("phone", "")
    online = profile.optBoolean("is_online", false)
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

 fun changeOnlineStatus(value: Boolean) {
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

    infoMessage = if (online) {
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

 fun refreshOrders() {
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
    infoMessage = "Список заказов обновлён"
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
    DriverApiClient.updateOrderStatus(
     orderId = orderId,
     status = nextStatus
    )
   },
   onResult = { _, error ->
    loading = false

    if (error != null) {
     errorMessage = error
    } else {
     infoMessage = "Статус заказа обновлён"
     refreshOrders()
    }
   }
  )
 }

 MaterialTheme(
  colorScheme = if (dark) {
   darkColorScheme(
    primary = VexaTeal,
    secondary = VexaTeal,
    background = VexaInk,
    surface = VexaNavy,
    onPrimary = VexaInk,
    onBackground = Color.White,
    onSurface = Color.White
   )
  } else {
   lightColorScheme(
    primary = VexaTeal,
    secondary = VexaTeal,
    background = VexaBackground,
    surface = Color.White,
    onPrimary = VexaInk,
    onBackground = VexaInk,
    onSurface = VexaInk
   )
  }
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
       text = "Сервер VEXA · 109.120.184.20",
       color = VexaMuted,
       fontSize = 11.sp
      )
     }
    }
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

       TextButton(
        onClick = {
         DriverApiClient.clearAccessToken()
         authorized = false
         online = false
         orders = emptyList()
         errorMessage = ""
         infoMessage = "Вы вышли из профиля"
        }
       ) {
        Text("Выйти")
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
          text = "Доходы, комиссия сервиса и задолженность",
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
         shape = RoundedCornerShape(14.dp),
         colors = ButtonDefaults.buttonColors(
          containerColor = VexaTeal,
          contentColor = VexaInk
         )
        ) {
         Text("Открыть")
        }
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
         enabled = !loading,
         colors = SwitchDefaults.colors(
          checkedThumbColor = Color.White,
          checkedTrackColor = VexaTeal,
          uncheckedThumbColor = Color.White,
          uncheckedTrackColor = Color.Gray
         )
        )
       }
      }
     }

     item {
      VexaCard(
       dark = dark,
       modifier = Modifier
      ) {
       SectionTitle(
        title = "Карта",
        subtitle = "Ваше местоположение · Оболенск",
        color = foregroundColor
       )

       ClipMapContainer {
        DriverMap(
         modifier = Modifier
          .fillMaxWidth()
          .height(300.dp)
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
     item {
      VexaCard(dark = dark) {
       SectionTitle(
        title = "Внешний вид",
        subtitle = "Настройте оформление приложения",
        color = foregroundColor
       )

       Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp)
       ) {
        listOf(
         "Дневная",
         "Ночная",
         "Системная"
        ).forEach { option ->
         FilterChip(
          selected = theme == option,
          onClick = { theme = option },
          label = {
           Text(option, fontSize = 11.sp)
          },
          colors = FilterChipDefaults.filterChipColors(
           selectedContainerColor = VexaTeal.copy(alpha = 0.2f),
           selectedLabelColor = if (dark) VexaTeal else VexaInk
          )
         )
        }
       }

       HorizontalDivider(
        color = if (dark) Color.White.copy(alpha = 0.08f)
        else Color.Black.copy(alpha = 0.06f)
       )

       Text(
        text = "Звуковой профиль",
        color = foregroundColor,
        fontWeight = FontWeight.SemiBold,
        fontSize = 13.sp
       )

       val soundNames = listOf(
        "classic",
        "modern",
        "soft",
        "dynamic",
        "calm",
        "premium"
       )

       soundNames.chunked(3).forEach { rowItems ->
        Row(
         modifier = Modifier.fillMaxWidth(),
         horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
         rowItems.forEach { option ->
          FilterChip(
           modifier = Modifier.weight(1f),
           selected = sound == option,
           onClick = { sound = option },
           label = {
            Text(
             option,
             fontSize = 10.sp,
             maxLines = 1
            )
           },
           colors = FilterChipDefaults.filterChipColors(
            selectedContainerColor = VexaTeal.copy(alpha = 0.2f)
           )
          )
         }
        }
       }

       Text(
        text = "Выбор звукового профиля пока сохраняется только на экране приложения.",
        color = secondaryText,
        fontSize = 10.sp
       )
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
       text = "VEXA Driver · Оболенск",
       modifier = Modifier
        .fillMaxWidth()
        .padding(top = 8.dp),
       color = secondaryText,
       fontSize = 10.sp
      )
     }
    }
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
