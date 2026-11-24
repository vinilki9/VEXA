
package ru.vexa.client

import android.os.Bundle
import ru.vexa.offline.OfflineMapMode
import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.lightColorScheme
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject

import java.time.Instant
import java.time.OffsetDateTime
import java.util.UUID
import kotlin.math.abs

private val Teal = VexaDesign.mutedTeal
private val Ink = Color(0xFF111827)
private val PanelWhite = Color.White
private val CancelRed = Color(0xFFE53935)

private fun parsePriceQuoteExpiry(value: String): Instant? {
 return runCatching {
  Instant.parse(value)
 }.getOrNull() ?: runCatching {
  OffsetDateTime.parse(value).toInstant()
 }.getOrNull()
}

private fun lastKnownClientLocation(context: Context): Location? {
 val fine = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
 val coarse = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
 if (!fine && !coarse) return null
 val service = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
 return try {
  val provider = when {
   service.isProviderEnabled(LocationManager.GPS_PROVIDER) -> LocationManager.GPS_PROVIDER
   service.isProviderEnabled(LocationManager.NETWORK_PROVIDER) -> LocationManager.NETWORK_PROVIDER
   else -> return null
  }
  service.getLastKnownLocation(provider)
 } catch (_: SecurityException) { null }
}

class MainActivity : ComponentActivity() {
 override fun onCreate(savedInstanceState: Bundle?) {
  super.onCreate(savedInstanceState)
  setContent {
   val context = LocalContext.current
   var selectedTheme by remember { mutableStateOf(VexaClientPreferences.getTheme(context)) }
   var defaultPayment by remember { mutableStateOf(VexaClientPreferences.getDefaultPayment(context)) }
   var settingsOpen by rememberSaveable { mutableStateOf(false) }
   var settingsRevision by remember { mutableIntStateOf(0) }
   val useDarkTheme = when (selectedTheme) {
    VexaThemeMode.DARK -> true
    VexaThemeMode.LIGHT -> false
    VexaThemeMode.SYSTEM -> androidx.compose.foundation.isSystemInDarkTheme()
   }
   val colors = if (useDarkTheme) VexaDesign.darkScheme() else VexaDesign.lightScheme()

   MaterialTheme(colorScheme = colors) {
    ClientScreen(
     onOpenSettings = { settingsOpen = true },
     defaultPayment = defaultPayment,
     settingsRevision = settingsRevision
    )
    if (settingsOpen) {
     BackHandler { settingsRevision++; settingsOpen = false }
     // Separate full-screen dialog keeps map, form and active order state alive
     // while the user edits settings; back or the top arrow closes this page.
     Dialog(
      onDismissRequest = { settingsRevision++; settingsOpen = false },
      properties = DialogProperties(usePlatformDefaultWidth = false)
     ) {
      VexaClientSettingsScreen(
       themeMode = selectedTheme,
       onThemeModeChange = { next ->
        VexaClientPreferences.setTheme(context, next)
        selectedTheme = next
       },
       defaultPayment = defaultPayment,
       onDefaultPaymentChange = { next ->
        VexaClientPreferences.setDefaultPayment(context, next)
        defaultPayment = next
       },
       onBack = { settingsRevision++; settingsOpen = false }
      )
     }
    }
   }
  }
 }
}

@Composable
fun ClientScreen(onOpenSettings: () -> Unit, defaultPayment: String, settingsRevision: Int = 0) {
 // All existing order state survives navigation to the settings dialog.
 val Ink = MaterialTheme.colorScheme.onSurface
 val PanelWhite = MaterialTheme.colorScheme.surface
 val secondaryText = MaterialTheme.colorScheme.onSurfaceVariant

 var panelFraction by remember { mutableFloatStateOf(0.45f) }
 var pickup by remember { mutableStateOf("") }
 var destination by remember { mutableStateOf("") }
 var selectedPickup by remember { mutableStateOf<AddressResult?>(null) }
 var selectedDestination by remember { mutableStateOf<AddressResult?>(null) }
 val context = LocalContext.current
 var gpsError by remember { mutableStateOf("") }
 val gpsRequest = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { granted ->
  if (!granted.values.any { it }) gpsError = "Разрешите доступ к геопозиции" else {
   val current = lastKnownClientLocation(context)
   if (current == null) gpsError = "GPS пока не определил позицию" else {
    selectedPickup = AddressResult("Моя геопозиция", current.latitude, current.longitude)
    pickup = "Моя геопозиция"
    gpsError = ""
   }
  }
 }
 var routeSummary by remember { mutableStateOf<String?>(null) }
 var routeError by remember { mutableStateOf<String?>(null) }
 var routeLine by remember { mutableStateOf<List<MapPoint>>(emptyList()) }

 LaunchedEffect(selectedPickup, selectedDestination, OfflineMapMode.changeCounter.intValue) {
  routeLine = emptyList()
  routeSummary = null
  routeError = null
  val start = selectedPickup ?: return@LaunchedEffect
  val end = selectedDestination ?: return@LaunchedEffect
  routeSummary = "Строим маршрут VEXA MAP..."
  try {
   val result = VexaRouting.route(context, start, end)
   routeLine = result.line
   routeSummary = "${if (result.offline) "Офлайн-предпросмотр (не для расчёта тарифа)" else "Маршрут"}: %.1f км, %d мин".format(
    java.util.Locale("ru", "RU"), result.meters / 1000, (result.seconds / 60).toInt()
   )
  } catch (error: Exception) {
   if (error is kotlinx.coroutines.CancellationException) throw error
   routeSummary = null
   routeError = error.message ?: "VEXA MAP: построение маршрута недоступно"
  }
 }

 var pickupSuggestions by remember {
  mutableStateOf<List<AddressResult>>(emptyList())
 }

 var pickupSearching by remember {
  mutableStateOf(false)
 }

 var pickupError by remember {
  mutableStateOf<String?>(null)
 }

 var destinationSuggestions by remember {
  mutableStateOf<List<AddressResult>>(emptyList())
 }

 var destinationSearching by remember {
  mutableStateOf(false)
 }

 var destinationError by remember {
  mutableStateOf<String?>(null)
 }

 LaunchedEffect(pickup) {
  val query = pickup.trim()

  if (
   query.length < 1 ||
   query == "Моя геопозиция" ||
   selectedPickup?.name == pickup
  ) {
   pickupSuggestions = emptyList()
   pickupSearching = false
   pickupError = null
   return@LaunchedEffect
  }

  delay(450)

  pickupSearching = true
  pickupError = null

  try {
   val results = AddressSearch.search(context, query)
   if (pickup.trim() == query) {
    pickupSuggestions = results
    pickupSearching = false
   }
  } catch (error: Exception) {
   if (error is kotlinx.coroutines.CancellationException) throw error
   if (pickup.trim() == query) {
    pickupError = error.message ?: "Поиск VEXA MAP недоступен"
    pickupSearching = false
    pickupSuggestions = emptyList()
   }
  }
 }

 LaunchedEffect(destination) {
  val query = destination.trim()

  if (
   query.length < 3 ||
   selectedDestination?.name == destination
  ) {
   destinationSuggestions = emptyList()
   destinationSearching = false
   destinationError = null
   return@LaunchedEffect
  }

  delay(450)

  destinationSearching = true
  destinationError = null

  try {
   val results = AddressSearch.search(context, query)
   if (destination.trim() == query) {
    destinationSuggestions = results
    destinationSearching = false
   }
  } catch (error: Exception) {
   if (error is kotlinx.coroutines.CancellationException) throw error
   if (destination.trim() == query) {
    destinationError = error.message ?: "Поиск VEXA MAP недоступен"
    destinationSearching = false
    destinationSuggestions = emptyList()
   }
  }
 }

 var tariff by remember {
  mutableStateOf("Economy")
 }

 var customerName by remember {
  mutableStateOf("")
 }

 var cargoVehicle by remember {
  mutableStateOf("Универсал")
 }

 var cargoDescription by remember {
  mutableStateOf("")
 }

 var cargoLoaders by remember {
  mutableIntStateOf(0)
 }

 var child by remember {
  mutableStateOf(false)
 }

 var animal by remember {
  mutableStateOf(false)
 }

 var payment by remember {
  mutableStateOf(defaultPayment)
 }
 LaunchedEffect(defaultPayment) { payment = defaultPayment }

 var pickupComment by remember { mutableStateOf("") }
 var home by remember(context) { mutableStateOf(VexaSavedPlaces.load(context, VexaSavedPlaces.HOME)) }
 var work by remember(context) { mutableStateOf(VexaSavedPlaces.load(context, VexaSavedPlaces.WORK)) }
 var savedPlaceMessage by remember { mutableStateOf("") }
 val signedInPhone = if (ApiClient.getAccessToken().isNullOrBlank()) ""
     else ApiClient.getPassengerPhone().orEmpty()
 LaunchedEffect(signedInPhone, settingsRevision) {
  home = VexaSavedPlaces.load(context, VexaSavedPlaces.HOME)
  work = VexaSavedPlaces.load(context, VexaSavedPlaces.WORK)
 }

 var optionsMenu by remember {
  mutableStateOf(false)
 }

 var paymentMenu by remember {
  mutableStateOf(false)
 }

 var orderCreated by remember {
  mutableStateOf(false)
 }
 var orderTerminal by remember { mutableStateOf(false) }

 var orderSubmitting by remember {
  mutableStateOf(false)
 }

 var orderPublicNumber by remember {
  mutableStateOf<String?>(null)
 }

 var orderError by remember {
  mutableStateOf<String?>(null)
 }

 var pricePreview by remember {
  mutableStateOf<JSONObject?>(null)
 }

 var pricePreviewSignature by remember {
  mutableStateOf<String?>(null)
 }

 var priceQuoteSecondsRemaining by remember {
  mutableIntStateOf(0)
 }

 var priceQuoteExpired by remember {
  mutableStateOf(false)
 }

 LaunchedEffect(pricePreview) {
  val preview = pricePreview

  if (preview == null) {
   priceQuoteSecondsRemaining = 0
   priceQuoteExpired = false
   return@LaunchedEffect
  }

  val expiresAtValue = preview.optString(
   "price_quote_expires_at",
   ""
  )

  val expiresAt = parsePriceQuoteExpiry(expiresAtValue)

  if (expiresAt == null) {
   priceQuoteSecondsRemaining = 0
   priceQuoteExpired = true
   return@LaunchedEffect
  }

  while (true) {
   val remainingMillis =
    java.time.Duration.between(
     Instant.now(),
     expiresAt
    ).toMillis()

   if (remainingMillis <= 0L) {
    priceQuoteSecondsRemaining = 0
    priceQuoteExpired = true
    break
   }

   priceQuoteSecondsRemaining =
    ((remainingMillis + 999L) / 1000L)
     .coerceAtMost(Int.MAX_VALUE.toLong())
     .toInt()

   priceQuoteExpired = false

   delay(1000)
  }
 }

 var showPassengerAuthDialog by remember {
  mutableStateOf(false)
 }
 var tripHistoryOpen by remember { mutableStateOf(false) }

 val currentPricePreviewSignature = listOf(
  tariff,
  customerName.trim(),
  selectedPickup?.name.orEmpty(),
  selectedPickup?.latitude?.toString().orEmpty(),
  selectedPickup?.longitude?.toString().orEmpty(),
  selectedDestination?.name.orEmpty(),
  selectedDestination?.latitude?.toString().orEmpty(),
  selectedDestination?.longitude?.toString().orEmpty(),
  payment,
  child.toString(),
  animal.toString(),
  cargoVehicle,
  cargoDescription.trim(),
  cargoLoaders.toString(),
  pickupComment.trim()
 ).joinToString("|")
 val coroutineScope = rememberCoroutineScope()

 val hasCurrentPricePreview =
  pricePreview != null &&
   pricePreviewSignature == currentPricePreviewSignature &&
   !priceQuoteExpired

 val animatedFraction by animateFloatAsState(
  targetValue = panelFraction,
  label = "PanelHeight"
 )

 val configuration = LocalConfiguration.current
 val density = LocalDensity.current

 val screenHeightPx = with(density) {
  configuration.screenHeightDp.dp.toPx()
 }

 Box(
  modifier = Modifier.fillMaxSize()
 ) {
  VexaMapView(
   pickup = selectedPickup,
   destination = selectedDestination,
   route = routeLine,
   modifier = Modifier.fillMaxSize()
  )

  // Settings entry point is pinned to the upper-right corner of the map.
  Surface(
   modifier = Modifier
    .align(Alignment.TopEnd)
    .statusBarsPadding()
    .padding(top = 12.dp, end = 16.dp),
   shape = RoundedCornerShape(16.dp),
   color = MaterialTheme.colorScheme.surface,
   shadowElevation = 6.dp
  ) {
   IconButton(
    onClick = onOpenSettings,
    modifier = Modifier.size(48.dp)
   ) {
    Icon(
     imageVector = Icons.Default.MoreVert,
     contentDescription = "Открыть настройки приложения",
     tint = MaterialTheme.colorScheme.onSurface
    )
   }
  }

  Surface(
   modifier = Modifier
    .align(Alignment.BottomCenter)
    .fillMaxWidth()
    .height(
     configuration.screenHeightDp.dp * animatedFraction
    ),
   color = PanelWhite,
   shape = RoundedCornerShape(
    topStart = 24.dp,
    topEnd = 24.dp
   ),
   shadowElevation = 12.dp
  ) {
   Column(
    modifier = Modifier.fillMaxSize()
   ) {
    Box(
     modifier = Modifier
      .fillMaxWidth()
      .height(34.dp)
      .pointerInput(screenHeightPx) {
       detectVerticalDragGestures(
        onVerticalDrag = { change, dragAmount ->
         change.consume()

         panelFraction = (
                 panelFraction -
                         dragAmount / screenHeightPx
                 ).coerceIn(0.20f, 0.80f)
        },
        onDragEnd = {
         val positions = listOf(
          0.15f,
          0.45f,
          0.80f
         )

         panelFraction = positions.minBy {
          abs(it - panelFraction)
         }
        }
       )
      },
     contentAlignment = Alignment.Center
    ) {
     Box(
      modifier = Modifier
       .width(42.dp)
       .height(5.dp)
       .clip(RoundedCornerShape(50))
       .background(Color.LightGray)
     )
    }

    Column(
     modifier = Modifier
      .fillMaxSize()
      .verticalScroll(rememberScrollState())
      .padding(
       start = 18.dp,
       end = 18.dp,
       bottom = 20.dp
      ),
     verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
     Row(
      verticalAlignment = Alignment.CenterVertically
     ) {
      Text(
       "VEXA",
       color = Teal,
       fontSize = 24.sp,
       style = MaterialTheme.typography.headlineMedium
      )

      Spacer(Modifier.width(10.dp))

      Text(
       "ПАССАЖИР",
       color = Ink,
       fontSize = 11.sp
      )
     }

     Row(verticalAlignment = Alignment.CenterVertically) {
      Text(
       "Куда едем?",
       modifier = Modifier.weight(1f),
       color = Ink,
       style = MaterialTheme.typography.titleLarge
      )
      OutlinedButton(onClick = { tripHistoryOpen = true }) {
       Text("Мои поездки")
      }
     }


     VexaClientQuickDestinations(
      home = home.takeUnless { ApiClient.getAccessToken().isNullOrBlank() },
      work = work.takeUnless { ApiClient.getAccessToken().isNullOrBlank() },
      hasSelectedDestination = selectedDestination != null,
      canEditRoute = !orderCreated || orderTerminal,
      onUse = { place ->
       destination = place.name
       selectedDestination = place
       destinationSuggestions = emptyList()
       pricePreview = null
       pricePreviewSignature = null
       savedPlaceMessage = "Адрес выбран. Стоимость будет рассчитана заново."
      },
      onSave = { kind ->
       selectedDestination?.let { point ->
        runCatching { VexaSavedPlaces.save(context, kind, point) }
         .onSuccess {
          home = VexaSavedPlaces.load(context, VexaSavedPlaces.HOME)
          work = VexaSavedPlaces.load(context, VexaSavedPlaces.WORK)
          savedPlaceMessage = "Адрес сохранён только на этом устройстве"
         }.onFailure { savedPlaceMessage = it.message.orEmpty() }
       }
      }
     )
     if (savedPlaceMessage.isNotBlank()) {
      Text(savedPlaceMessage, color = secondaryText, fontSize = 11.sp)
     }

     Box {
      Column {
       OutlinedTextField(
        value = pickup,
        onValueChange = {
         pickup = it
         selectedPickup = null
         pickupError = null
         orderError = null
        },
        label = {
         Text("Откуда")
        },
        modifier = Modifier.fillMaxWidth(),
        singleLine = true
       )

       OutlinedButton(
        onClick = {
         val point = lastKnownClientLocation(context)
         if (point != null) {
          selectedPickup = AddressResult("Моя геопозиция", point.latitude, point.longitude)
          pickup = "Моя геопозиция"
          gpsError = ""
         } else {
          gpsRequest.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
         }
        },
        modifier = Modifier.fillMaxWidth()
       ) { Text("Использовать моё местоположение") }
       if (gpsError.isNotBlank()) Text(gpsError, color = CancelRed, fontSize = 11.sp)
       OutlinedTextField(
        value = pickupComment,
        onValueChange = { if (it.length <= 500) pickupComment = it },
        label = { Text("Комментарий к подаче (подъезд, вход, ориентир)") },
        modifier = Modifier.fillMaxWidth(),
        singleLine = false,
        maxLines = 3
       )

       if (pickupSearching) {
        Text(
         "Ищем адрес...",
         color = secondaryText,
         fontSize = 11.sp
        )
       }

       pickupError?.let {
        Text(
         it,
         color = CancelRed,
         fontSize = 11.sp
        )
       }
      }

      DropdownMenu(
       expanded = pickupSuggestions.isNotEmpty(),
       onDismissRequest = {
        pickupSuggestions = emptyList()
       },
       modifier = Modifier.fillMaxWidth(0.92f)
      ) {
       pickupSuggestions.forEach { address ->
        DropdownMenuItem(
         text = {
          Text(address.name)
         },
         onClick = {
          pickup = address.name
          selectedPickup = address
          pickupSuggestions = emptyList()
          pickupError = null
         }
        )
       }
      }
     }

     Box {
      Column {
       OutlinedTextField(
        value = destination,
        onValueChange = {
         destination = it
         selectedDestination = null
         destinationError = null
         orderError = null
        },
        label = {
         Text("Куда")
        },
        modifier = Modifier.fillMaxWidth(),
        singleLine = true
       )

       if (destinationSearching) {
        Text(
         "Ищем адрес...",
         color = secondaryText,
         fontSize = 11.sp
        )
       }

       destinationError?.let {
        Text(
         it,
         color = CancelRed,
         fontSize = 11.sp
        )
       }
      }

      DropdownMenu(
       expanded = destinationSuggestions.isNotEmpty(),
       onDismissRequest = {
        destinationSuggestions = emptyList()
       },
       modifier = Modifier.fillMaxWidth(0.92f)
      ) {
       destinationSuggestions.forEach { address ->
        DropdownMenuItem(
         text = {
          Text(address.name)
         },
         onClick = {
          destination = address.name
          selectedDestination = address
          destinationSuggestions = emptyList()
          destinationError = null
         }
        )
       }
      }
     }

     routeSummary?.let { summary ->
      Text(
       summary,
       color = Teal,
       style = MaterialTheme.typography.titleMedium
      )
     }

     routeError?.let { error ->
      Text(
       error,
       color = CancelRed,
       fontSize = 11.sp
      )
     }

     Text(
      "Ваше имя *",
      color = Ink,
      style = MaterialTheme.typography.titleMedium
     )

     OutlinedTextField(
      value = customerName,
      onValueChange = {
       customerName = it
       orderError = null
      },
      label = {
       Text("Имя")
      },
      placeholder = {
       Text("Введите ваше имя")
      },
      modifier = Modifier.fillMaxWidth(),
      singleLine = true
     )

     Text(
      "Имя обязательно для оформления заказа и будет видно водителю.",
      color = secondaryText,
      fontSize = 11.sp
     )

     Text(
      "Тариф",
      color = Ink,
      style = MaterialTheme.typography.titleMedium
     )

     Row(
      modifier = Modifier.horizontalScroll(
       rememberScrollState()
      ),
      horizontalArrangement = Arrangement.spacedBy(6.dp)
     ) {
      listOf(
       "Economy",
       "Comfort",
       "Comfort+",
       "Business",
       "Premier",
       "Грузовой"
      ).forEach { item ->
       FilterChip(
        selected = tariff == item,
        onClick = {
         tariff = item
         orderError = null
        },
        label = {
         Text(item, fontSize = 11.sp)
        },
        colors = FilterChipDefaults.filterChipColors(
         selectedContainerColor =
          Teal.copy(alpha = 0.18f)
        )
       )
      }
     }

     if (tariff == "Грузовой") {
      Text(
       "Тип грузового автомобиля",
       color = Ink,
       style = MaterialTheme.typography.titleSmall
      )

      Column(
       verticalArrangement = Arrangement.spacedBy(6.dp)
      ) {
       listOf(
        "Универсал",
        "Каблук / небольшой фургон",
        "Средний грузовой фургон",
        "Газель"
       ).forEach { vehicle ->
        FilterChip(
         selected = cargoVehicle == vehicle,
         onClick = {
          cargoVehicle = vehicle
         },
         label = {
          Text(vehicle)
         }
        )
       }
      }

      OutlinedTextField(
       value = cargoDescription,
       onValueChange = {
        cargoDescription = it
       },
       label = {
        Text("Описание груза")
       },
       modifier = Modifier.fillMaxWidth(),
       minLines = 2
      )

      Text(
       "Дополнительная услуга",
       color = Ink,
       style = MaterialTheme.typography.titleSmall
      )

      Text("Количество грузчиков")

      Row(
       horizontalArrangement = Arrangement.spacedBy(8.dp)
      ) {
       (0..4).forEach { count ->
        FilterChip(
         selected = cargoLoaders == count,
         onClick = {
          cargoLoaders = count
         },
         label = {
          Text(
           if (count == 0) {
            "Без грузчиков"
           } else {
            "$count"
           }
          )
         }
        )
       }
      }
     }

     Box {
      OutlinedButton(
       onClick = {
        optionsMenu = true
       },
       modifier = Modifier.fillMaxWidth()
      ) {
       Text("Дополнительно ▾")
      }

      DropdownMenu(
       expanded = optionsMenu,
       onDismissRequest = {
        optionsMenu = false
       }
      ) {
       DropdownMenuItem(
        text = {
         Row(
          verticalAlignment = Alignment.CenterVertically
         ) {
          Checkbox(
           checked = child,
           onCheckedChange = null
          )
          Text("Детское кресло +100 ₽")
         }
        },
        onClick = {
         child = !child
        }
       )

       DropdownMenuItem(
        text = {
         Row(
          verticalAlignment = Alignment.CenterVertically
         ) {
          Checkbox(
           checked = animal,
           onCheckedChange = null
          )
          Text("Перевозка животного +100 ₽")
         }
        },
        onClick = {
         animal = !animal
        }
       )
      }
     }

     Text(
      "Опции: " +
              listOfNotNull(
               if (child) "Детское кресло" else null,
               if (animal) "Животное" else null
              ).ifEmpty {
               listOf("Не выбраны")
              }.joinToString(", "),
      color = secondaryText,
      fontSize = 12.sp
     )

     Box {
      OutlinedButton(
       onClick = {
        paymentMenu = true
       },
       modifier = Modifier.fillMaxWidth()
      ) {
       Text("Оплата: $payment  ▾")
      }

      DropdownMenu(
       expanded = paymentMenu,
       onDismissRequest = {
        paymentMenu = false
       }
      ) {
       listOf(
        "Наличные",
        "Перевод водителю",
        "Банковская карта",
        "СБП"
       ).forEach { method ->
        DropdownMenuItem(
         text = {
          Text(method)
         },
         onClick = {
          payment = method
          paymentMenu = false
         }
        )
       }
      }
     }

     // Здесь отображается карточка предварительного расчёта.
     // Пассажиру показываем только итоговую стоимость поездки.
     if (
      pricePreview != null &&
      pricePreviewSignature == currentPricePreviewSignature
     ) {
      val preview = pricePreview!!

      val totalPrice = preview.optString(
       "price_rub",
       ""
      )

      val minutes = priceQuoteSecondsRemaining / 60
      val seconds = priceQuoteSecondsRemaining % 60

      Surface(
       modifier = Modifier.fillMaxWidth(),
       shape = RoundedCornerShape(16.dp),
       color = if (priceQuoteExpired) {
        CancelRed.copy(alpha = 0.08f)
       } else {
        Teal.copy(alpha = 0.10f)
       }
      ) {
       Column(
        modifier = Modifier.padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
       ) {
        Text(
         if (priceQuoteExpired) {
          "Расчёт стоимости устарел"
         } else {
          "Стоимость поездки"
         },
         color = if (priceQuoteExpired) CancelRed else Ink,
         style = MaterialTheme.typography.titleMedium
        )

        Text(
         "$totalPrice ₽",
         color = if (priceQuoteExpired) Color.Gray else Ink,
         fontSize = 30.sp,
         fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
        )

        if (priceQuoteExpired) {
         Text(
          "Срок действия расчёта истёк. " +
                  "Для заказа необходимо рассчитать стоимость заново.",
          color = CancelRed,
          fontSize = 12.sp
         )
        } else {
         Text(
          "Расчёт действителен ещё: %02d:%02d".format(
           minutes,
           seconds
          ),
          color = if (priceQuoteSecondsRemaining <= 20) {
           CancelRed
          } else {
           secondaryText
          },
          fontSize = 12.sp
         )

         Text(
          "После подтверждения заказа стоимость фиксируется.",
          color = secondaryText,
          fontSize = 11.sp
         )
        }
       }
      }
     }

     orderError?.let { error ->
      Text(
       text = error,
       color = CancelRed,
       fontSize = 12.sp
      )
     }

     orderPublicNumber?.let { number ->
      Text(
       text = "Номер заказа: $number",
       color = Teal,
       style = MaterialTheme.typography.titleMedium
      )

      PassengerOrderStatusPanel(
       orderIdentifier = number,
       onTerminal = { orderTerminal = true },
       onNewTrip = {
        orderPublicNumber = null
        orderCreated = false
        orderTerminal = false
        pricePreview = null
        pricePreviewSignature = null
        orderError = null
       }
      )
      OutlinedButton(
       onClick = {
        runCatching { VexaRideShare.share(context, number, pickup, destination) }
         .onFailure { orderError = "Не удалось открыть системное меню отправки" }
       },
       modifier = Modifier.fillMaxWidth()
      ) { Text("Поделиться информацией о поездке") }
      Text("В реальном времени поездка через эту кнопку пока не отслеживается.",
       color = secondaryText, fontSize = 10.sp)
     }

     Button(
      onClick = {
       if (orderCreated || orderSubmitting) {
        return@Button
       }

       if (ApiClient.getAccessToken().isNullOrBlank()) {
        showPassengerAuthDialog = true
        return@Button
       }

       if (customerName.isBlank()) {
        orderError = "Укажите ваше имя."
        return@Button
       }

       val pickupAddress = selectedPickup
       val destinationAddress = selectedDestination

       if (pickupAddress == null) {
        orderError = "Выберите адрес подачи из подсказок."
        return@Button
       }

       if (destinationAddress == null) {
        orderError = "Выберите адрес назначения из подсказок."
        return@Button
       }

       if (routeLine.isEmpty()) {
        orderError = "Дождитесь построения маршрута."
        return@Button
       }

       val requestSignature =
        currentPricePreviewSignature

       val hasCurrentPreview =
        pricePreview != null &&
         pricePreviewSignature == requestSignature &&
         !priceQuoteExpired

       orderSubmitting = true
       orderError = null

       coroutineScope.launch {
        try {
         if (!hasCurrentPreview) {
          val preview =
           PassengerOrderRepository.previewOrderPrice(
            tariffLabel = tariff,
            customerName = customerName.trim(),
            pickupAddress = pickupAddress.name,
            destinationAddress = destinationAddress.name,
            pickupLatitude = pickupAddress.latitude,
            pickupLongitude = pickupAddress.longitude,
            destinationLatitude = destinationAddress.latitude,
            destinationLongitude = destinationAddress.longitude,
            paymentLabel = payment,
            childSeat = child,
            animalTransport = animal,
            cargoVehicle = cargoVehicle,
            cargoDescription = cargoDescription,
            cargoLoaders = cargoLoaders,
            pickupComment = pickupComment
           )

          pricePreview = preview
          pricePreviewSignature = requestSignature

         } else {
          val priceQuoteToken =
           pricePreview?.optString("price_quote_token").orEmpty()

          if (priceQuoteToken.isBlank()) {
           throw IllegalStateException(
            "Сервер не вернул токен расчёта стоимости. " +
                    "Рассчитайте стоимость заново."
           )
          }

          // Один токен ценового предложения всегда даёт один
          // и тот же ключ. Повтор после сетевой ошибки не создаст
          // второй заказ, если сервер уже обработал первый запрос.
          val idempotencyKey = UUID.nameUUIDFromBytes(
           priceQuoteToken.toByteArray(Charsets.UTF_8)
          ).toString()

          val response =
           PassengerOrderRepository.createOrder(
            tariffLabel = tariff,
            customerName = customerName.trim(),
            pickupAddress = pickupAddress.name,
            destinationAddress = destinationAddress.name,
            pickupLatitude = pickupAddress.latitude,
            pickupLongitude = pickupAddress.longitude,
            destinationLatitude = destinationAddress.latitude,
            destinationLongitude = destinationAddress.longitude,
            paymentLabel = payment,
            childSeat = child,
            animalTransport = animal,
            cargoVehicle = cargoVehicle,
            cargoDescription = cargoDescription,
            cargoLoaders = cargoLoaders,
            pickupComment = pickupComment,
            priceQuoteToken = priceQuoteToken,
            idempotencyKey = idempotencyKey
           )

          val publicNumber =
           response.optString("public_number")

          orderPublicNumber =
           publicNumber.ifBlank {
            response.optString("id")
           }

          orderCreated = true
          orderTerminal = false
         }
        } catch (error: Exception) {
         val errorMessage = error.message
          ?: "Не удалось выполнить запрос. Попробуйте ещё раз."

         val requiresPriceRecalculation =
          errorMessage.contains(
           "Ошибка сервера: 409"
          ) && (
           errorMessage.contains(
            "ценовое предложение",
            ignoreCase = true
           ) ||
           errorMessage.contains(
            "Рассчитайте стоимость повторно",
            ignoreCase = true
           ) ||
           errorMessage.contains(
            "Параметры заказа изменились",
            ignoreCase = true
           )
          )

         if (requiresPriceRecalculation) {
          pricePreview = null
          pricePreviewSignature = null

          orderError =
           "Срок действия расчёта истёк или параметры цены изменились. " +
                   "Проверьте стоимость и нажмите «Рассчитать стоимость» ещё раз."
         } else {
          orderError = errorMessage
         }
        } finally {
         orderSubmitting = false
        }
       }
      },
      enabled = !orderSubmitting && !orderCreated,
      modifier = Modifier
       .fillMaxWidth()
       .height(54.dp),
      colors = ButtonDefaults.buttonColors(
       containerColor = if (orderCreated) {
        Color.Gray
       } else {
        Teal
       }
      ),
      shape = RoundedCornerShape(14.dp)
     ) {
      if (orderSubmitting) {
       CircularProgressIndicator(
        modifier = Modifier.size(22.dp),
        color = Color.White,
        strokeWidth = 2.dp
       )
      } else {
       Text(
        text = when {
         orderCreated -> "Заказ создан"
         hasCurrentPricePreview -> "Подтвердить и заказать"
         else -> "Рассчитать стоимость"
        },
        color = MaterialTheme.colorScheme.onPrimary,
        fontSize = 16.sp
       )
      }
     }

     Text(
      "VEXA такси.",
      color = secondaryText,
      fontSize = 10.sp
     )
    }
   }
  }

  if (tripHistoryOpen) {
   VexaTripHistoryDialog(
    onDismiss = { tripHistoryOpen = false },
    onRepeatTrip = { previousPickup, previousDestination ->
     if (orderCreated && !orderTerminal) {
      orderError = "Сначала завершите текущий заказ. Новый маршрут пока не выбран."
      tripHistoryOpen = false
     } else {
      pickup = previousPickup.name
      destination = previousDestination.name
      selectedPickup = previousPickup
      selectedDestination = previousDestination
      pickupSuggestions = emptyList()
      destinationSuggestions = emptyList()
      pricePreview = null
      pricePreviewSignature = null
      orderCreated = false
      orderTerminal = false
      orderPublicNumber = null
      orderError = null
      panelFraction = 0.80f
      tripHistoryOpen = false
     }
    }
   )
  }

  if (showPassengerAuthDialog) {
   PassengerAuthDialog(
    onAuthenticated = {
     home = VexaSavedPlaces.load(context, VexaSavedPlaces.HOME)
     work = VexaSavedPlaces.load(context, VexaSavedPlaces.WORK)
     showPassengerAuthDialog = false
    },
    onDismiss = {
     showPassengerAuthDialog = false
    }
   )
  }
 }
}
