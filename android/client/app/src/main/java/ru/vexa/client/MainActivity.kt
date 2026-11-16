package ru.vexa.client

import ru.dgis.sdk.geometry.ComplexGeometry
import ru.dgis.sdk.geometry.PointGeometry
import androidx.compose.ui.platform.LocalContext
import ru.dgis.sdk.coordinates.Latitude
import ru.dgis.sdk.coordinates.Longitude
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject
import ru.dgis.sdk.map.*
import ru.dgis.sdk.geometry.GeoPointWithElevation
import ru.dgis.sdk.map.MarkerOptions
import ru.dgis.sdk.coordinates.GeoPoint
import ru.dgis.sdk.Duration
import ru.dgis.sdk.geometry.Elevation
import ru.dgis.sdk.compose.map.MapComposable
import ru.dgis.sdk.routing.*
import ru.vexa.driver.VexaApplication
import kotlin.math.abs

private val Teal = Color(0xFF1ED9C6)
private val Ink = Color(0xFF111827)
private val PanelWhite = Color.White
private val CancelRed = Color(0xFFE53935)

class MainActivity : ComponentActivity() {

 private lateinit var mapViewModel: DefaultMapControllerViewModel
 private lateinit var trafficRouter: TrafficRouter
 private var mapObjectManager: MapObjectManager? = null
 private var routeMapObjectSource: RouteMapObjectSource? = null
 private val dgisMapState = mutableStateOf<ru.dgis.sdk.map.Map?>(null)

 override fun onCreate(savedInstanceState: Bundle?) {
  super.onCreate(savedInstanceState)

  val sdkContext = (application as VexaApplication).sdkContext

  mapViewModel = DefaultMapControllerViewModel(
   sdkContext,
   MapControllerOptions(
    position = CameraPosition(
     point = GeoPoint(55.751244, 37.618423),
     zoom = Zoom(12.0f)
    )
   )
  )

  trafficRouter = TrafficRouter(sdkContext)

  lifecycleScope.launch {
   val map = mapViewModel.awaitMap()

   mapObjectManager = MapObjectManager(map)
   routeMapObjectSource = RouteMapObjectSource(
    sdkContext,
    RouteVisualizationType.NORMAL
   ).also(map::addSource)

   dgisMapState.value = map
  }

  setContent {
   ClientScreen(
    mapViewModel = mapViewModel,
    dgisMap = dgisMapState.value,
    mapObjectManager = mapObjectManager,
    routeMapObjectSource = routeMapObjectSource,
    trafficRouter = trafficRouter
   )
  }
 }

 override fun onDestroy() {
  routeMapObjectSource?.let { source ->
   dgisMapState.value?.removeSource(source)
  }

  routeMapObjectSource = null

  if (::trafficRouter.isInitialized) {
   trafficRouter.close()
  }

  if (::mapViewModel.isInitialized) {
   mapViewModel.close()
  }

  super.onDestroy()
 }
}

@Composable
fun ClientScreen(
 mapViewModel: DefaultMapControllerViewModel,
 dgisMap: ru.dgis.sdk.map.Map?,
 mapObjectManager: MapObjectManager?,
 routeMapObjectSource: RouteMapObjectSource?,
 trafficRouter: TrafficRouter
) {
 var panelFraction by remember {
  mutableFloatStateOf(0.45f)
 }

 var pickup by remember {
  mutableStateOf("")
 }

 var destination by remember {
  mutableStateOf("")
 }

 var selectedPickup by remember {
  mutableStateOf<AddressResult?>(null)
 }

 var selectedDestination by remember {
  mutableStateOf<AddressResult?>(null)
 }

 val sdkContext =
  (LocalContext.current.applicationContext as VexaApplication).sdkContext

 val pickupIcon = remember {
  imageFromResource(sdkContext, R.drawable.vexa_pickup_waving)
 }

 val destinationIcon = remember {
  imageFromResource(sdkContext, R.drawable.vexa_destination_flag)
 }

 var routeSummary by remember {
  mutableStateOf<String?>(null)
 }

 var routeError by remember {
  mutableStateOf<String?>(null)
 }

 var routeRequestVersion by remember {
  mutableStateOf(0)
 }

 var routeGeometry by remember {
  mutableStateOf<ComplexGeometry?>(null)
 }

 LaunchedEffect(
  selectedPickup,
  selectedDestination,
  routeGeometry,
  mapObjectManager,
  panelFraction
 ) {
  val source = routeMapObjectSource ?: return@LaunchedEffect

  val pickupAddress = selectedPickup
  val destinationAddress = selectedDestination

  routeRequestVersion += 1
  val requestVersion = routeRequestVersion

  source.clear()
  routeGeometry = null
  routeSummary = "Строим маршрут..."
  routeError = null

  if (pickupAddress == null || destinationAddress == null) {
   routeSummary = null
   return@LaunchedEffect
  }

  val startPoint = RouteSearchPoint(
   GeoPoint(
    pickupAddress.latitude,
    pickupAddress.longitude
   )
  )

  val finishPoint = RouteSearchPoint(
   GeoPoint(
    destinationAddress.latitude,
    destinationAddress.longitude
   )
  )

  val routeSearchOptions = RouteSearchOptions(
   TaxiRouteSearchOptions(
    CarRouteSearchOptions(
     routeSearchType = RouteSearchType.JAM
    )
   )
  )

  android.util.Log.d(
   "VEXA_ROUTING",
   "Запрос маршрута отправлен"
  )

  trafficRouter.findRoute(
   startPoint = startPoint,
   finishPoint = finishPoint,
   routeSearchOptions = routeSearchOptions
  ).onComplete(
   resultCallback = { routes ->
    if (requestVersion == routeRequestVersion) {
     if (routes.isEmpty()) {
      routeSummary = null
      routeError = "Маршрут для выбранных адресов не найден."
      routeGeometry = null

      android.util.Log.w(
       "VEXA_ROUTING",
       "SDK не вернул маршруты"
      )
     } else {
      routeGeometry = ComplexGeometry(
       routes[0].route.geometry.entries.map { entry ->
        PointGeometry(entry.value)
       }
      )

      source.replaceAllObjects(
       routes.mapIndexed { index, route ->
        RouteMapObject(
         trafficRoute = route,
         isActive = index == 0,
         index = RouteIndex(index.toLong())
        )
       }
      )

      android.util.Log.d(
       "VEXA_ROUTING",
       "Получено маршрутов: ${routes.size}"
      )
     }
    }
   },
   errorCallback = { error ->
    if (requestVersion == routeRequestVersion) {
     routeError =
      "Не удалось построить маршрут: ${error.message ?: "неизвестная ошибка"}"

     routeGeometry = null

     android.util.Log.e(
      "VEXA_ROUTING",
      "Ошибка построения маршрута",
      error
     )
    }
   }
  )

  trafficRouter.findBriefRouteInfos(
   searchPoints = listOf(
    BriefRouteInfoSearchPoints(startPoint, finishPoint)
   ),
   routeSearchOptions = routeSearchOptions
  ).onComplete(
   resultCallback = { routeInfos ->
    val routeInfo = routeInfos.firstOrNull()
    val carInfo = routeInfo?.extraInfo?.asCar

    if (requestVersion == routeRequestVersion && carInfo != null) {
     val kilometers =
      carInfo.length.millimeters / 1_000_000.0

     routeSummary = "Маршрут: %.1f км, %d мин".format(
      kilometers,
      routeInfo.duration.inMinutes
     )
    }
   },
   errorCallback = { error ->
    if (requestVersion == routeRequestVersion) {
     routeSummary = null

     android.util.Log.w(
      "VEXA_ROUTING",
      "Не удалось получить сводку маршрута",
      error
     )
    }
   }
  )
 }

 LaunchedEffect(
  selectedPickup,
  selectedDestination,
  mapObjectManager,
  panelFraction,
  routeGeometry
 ) {
  val manager = mapObjectManager ?: return@LaunchedEffect

  manager.removeAll()

  selectedPickup?.let { address ->
   manager.addObject(
    Marker(
     MarkerOptions(
      position = GeoPointWithElevation(
       latitude = Latitude(value = address.latitude),
       longitude = Longitude(value = address.longitude),
       elevation = Elevation(value = 0.0f)
      ),
      icon = pickupIcon,
      iconWidth = LogicalPixel(value = 32.0f),
      text = "Подача"
     )
    )
   )
  }

  selectedDestination?.let { address ->
   manager.addObject(
    Marker(
     MarkerOptions(
      position = GeoPointWithElevation(
       latitude = Latitude(value = address.latitude),
       longitude = Longitude(value = address.longitude),
       elevation = Elevation(value = 0.0f)
      ),
      icon = destinationIcon,
      iconWidth = LogicalPixel(value = 32.0f),
      text = "Назначение"
     )
    )
   )
  }

  val pickupAddress = selectedPickup
  val destinationAddress = selectedDestination
  val map = dgisMap

  if (
   pickupAddress != null &&
   destinationAddress != null &&
   map != null
  ) {
   val geometry = routeGeometry ?: return@LaunchedEffect

   val position = calcPosition(
    camera = map.camera,
    geometry = geometry,
    screenArea = Padding(
     left = 40,
     top = 100,
     right = 40,
     bottom = when {
      panelFraction >= 0.70f -> 1400
      panelFraction >= 0.30f -> 1000
      else -> 400
     }
    )
   )

   android.util.Log.d(
    "VEXA_CAMERA",
    "Расчет камеры выполнен"
   )

   map.camera.move(
    position,
    Duration.ofMilliseconds(900),
    CameraAnimationType.DEFAULT
   )
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

  AddressSearch.search(
   query = query,
   onResult = { results ->
    if (pickup.trim() == query) {
     pickupSuggestions = results
     pickupSearching = false
    }
   },
   onError = { error ->
    if (pickup.trim() == query) {
     pickupError = error
     pickupSearching = false
     pickupSuggestions = emptyList()
    }
   }
  )
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

  AddressSearch.search(
   query = query,
   onResult = { results ->
    if (destination.trim() == query) {
     destinationSuggestions = results
     destinationSearching = false
    }
   },
   onError = { error ->
    if (destination.trim() == query) {
     destinationError = error
     destinationSearching = false
     destinationSuggestions = emptyList()
    }
   }
  )
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

 var anonymous by remember {
  mutableStateOf(false)
 }

 var payment by remember {
  mutableStateOf("Наличные")
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

 var showPassengerAuthDialog by remember {
  mutableStateOf(false)
 }

 val isAnonymousOrder = anonymous || customerName.isBlank()
 val currentPricePreviewSignature = listOf(
  tariff,
  customerName.trim(),
  anonymous.toString(),
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
  cargoLoaders.toString()
 ).joinToString("|")
 val coroutineScope = rememberCoroutineScope()

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
  MapComposable(
   modifier = Modifier.fillMaxSize(),
   viewModel = mapViewModel,
   renderOptions = MapRenderOptions(),
   copyrightOptions = MapCopyrightOptions()
  )

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

     Text(
      "Куда едем?",
      color = Ink,
      style = MaterialTheme.typography.titleLarge
     )

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

       if (pickupSearching) {
        Text(
         "Ищем адрес...",
         color = Color.Gray,
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
         color = Color.Gray,
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
      "Ваше имя",
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
      if (isAnonymousOrder) {
       "Имя не указано или включена анонимность. " +
               "К стоимости подачи добавится 100 ₽."
      } else {
       "Ваше имя будет видно водителю."
      },
      color = if (isAnonymousOrder) CancelRed else Color.Gray,
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

       DropdownMenuItem(
        text = {
         Row(
          verticalAlignment = Alignment.CenterVertically
         ) {
          Checkbox(
           checked = anonymous,
           onCheckedChange = null
          )
          Text("Скрыть имя (+100 ₽)")
         }
        },
        onClick = {
         anonymous = !anonymous
        }
       )
      }
     }

     Text(
      "Опции: " +
              listOfNotNull(
               if (child) "Детское кресло" else null,
               if (animal) "Животное" else null,
               if (isAnonymousOrder) "Анонимность (+100 ₽)" else null
              ).ifEmpty {
               listOf("Не выбраны")
              }.joinToString(", "),
      color = Color.Gray,
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


     if (
      pricePreview != null &&
      pricePreviewSignature == currentPricePreviewSignature
     ) {
      val preview = pricePreview!!
      val breakdown = preview.optJSONObject(
       "dynamic_pricing_breakdown"
      ) ?: JSONObject()

      val reasons = breakdown.optJSONArray("reasons")

      val totalPrice = preview.optString(
       "price_rub",
       ""
      )

      val multiplier = preview.optString(
       "dynamic_pricing_multiplier",
       "1.00"
      )

      val driverDistance = preview.optString(
       "dynamic_driver_distance_km",
       ""
      )

      val dynamicAdjustment =
       preview.optInt(
        "fare_dynamic_adjustment_kopecks",
        0
       ) / 100.0

      Surface(
       modifier = Modifier.fillMaxWidth(),
       shape = RoundedCornerShape(16.dp),
       color = Teal.copy(alpha = 0.10f)
      ) {
       Column(
        modifier = Modifier.padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
       ) {
        Text(
         "Предварительная стоимость",
         color = Ink,
         style = MaterialTheme.typography.titleMedium
        )

        Text(
         "$totalPrice ₽",
         color = Ink,
         fontSize = 30.sp,
         fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
        )

        HorizontalDivider(
         color = Teal.copy(alpha = 0.25f)
        )

        Text(
         "Динамический коэффициент: ×$multiplier",
         color = Ink,
         fontSize = 13.sp
        )

        if (
         driverDistance.isNotBlank() &&
         driverDistance != "null"
        ) {
         Text(
          "Расстояние до свободного водителя: " +
                  "$driverDistance км",
          color = Color.DarkGray,
          fontSize = 12.sp
         )
        }

        if (dynamicAdjustment > 0.0) {
         Text(
          "Динамическая надбавка: " +
                  "%.2f ₽".format(dynamicAdjustment),
          color = Ink,
          fontSize = 13.sp
         )
        }

        if (reasons != null && reasons.length() > 0) {
         Text(
          "Причины изменения стоимости:",
          color = Ink,
          fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold,
          fontSize = 12.sp
         )

         for (index in 0 until reasons.length()) {
          Text(
           "• ${reasons.optString(index)}",
           color = Color.DarkGray,
           fontSize = 12.sp
          )
         }
        }

        Text(
         "Стоимость предварительная. " +
                 "Окончательная цена фиксируется сервером при оформлении заказа.",
         color = Color.DarkGray,
         fontSize = 11.sp
        )
       }
      }
     }


     if (
      pricePreview != null &&
      pricePreviewSignature == currentPricePreviewSignature
     ) {
      val preview = pricePreview!!
      val breakdown = preview.optJSONObject(
       "dynamic_pricing_breakdown"
      ) ?: JSONObject()

      val reasons = breakdown.optJSONArray("reasons")

      val totalPrice = preview.optString(
       "price_rub",
       ""
      )

      val multiplier = preview.optString(
       "dynamic_pricing_multiplier",
       "1.00"
      )

      val driverDistance = preview.optString(
       "dynamic_driver_distance_km",
       ""
      )

      val dynamicAdjustment =
       preview.optInt(
        "fare_dynamic_adjustment_kopecks",
        0
       ) / 100.0

      Surface(
       modifier = Modifier.fillMaxWidth(),
       shape = RoundedCornerShape(16.dp),
       color = Teal.copy(alpha = 0.10f)
      ) {
       Column(
        modifier = Modifier.padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
       ) {
        Text(
         "Предварительная стоимость",
         color = Ink,
         style = MaterialTheme.typography.titleMedium
        )

        Text(
         "$totalPrice ₽",
         color = Ink,
         fontSize = 30.sp,
         fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
        )

        HorizontalDivider(
         color = Teal.copy(alpha = 0.25f)
        )

        Text(
         "Динамический коэффициент: ×$multiplier",
         color = Ink,
         fontSize = 13.sp
        )

        if (
         driverDistance.isNotBlank() &&
         driverDistance != "null"
        ) {
         Text(
          "Расстояние до свободного водителя: " +
                  "$driverDistance км",
          color = Color.DarkGray,
          fontSize = 12.sp
         )
        }

        if (dynamicAdjustment > 0.0) {
         Text(
          "Динамическая надбавка: " +
                  "%.2f ₽".format(dynamicAdjustment),
          color = Ink,
          fontSize = 13.sp
         )
        }

        if (reasons != null && reasons.length() > 0) {
         Text(
          "Причины изменения стоимости:",
          color = Ink,
          fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold,
          fontSize = 12.sp
         )

         for (index in 0 until reasons.length()) {
          Text(
           "• ${reasons.optString(index)}",
           color = Color.DarkGray,
           fontSize = 12.sp
          )
         }
        }

        Text(
         "Стоимость предварительная. " +
                 "Окончательная цена фиксируется сервером при оформлении заказа.",
         color = Color.DarkGray,
         fontSize = 11.sp
        )
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
       orderIdentifier = number
      )
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

       if (routeGeometry == null) {
        orderError = "Дождитесь построения маршрута."
        return@Button
       }

       val requestSignature =
        currentPricePreviewSignature

       val hasCurrentPreview =
        pricePreview != null &&
                pricePreviewSignature == requestSignature

       orderSubmitting = true
       orderError = null

       coroutineScope.launch {
        try {
         if (!hasCurrentPreview) {
          val preview =
           PassengerOrderRepository.previewOrderPrice(
            tariffLabel = tariff,
            customerName = customerName.trim(),
            anonymous = anonymous,
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
            cargoLoaders = cargoLoaders
           )

          pricePreview = preview
          pricePreviewSignature = requestSignature

         } else {
          val response =
           PassengerOrderRepository.createOrder(
            tariffLabel = tariff,
            customerName = customerName.trim(),
            anonymous = anonymous,
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
            cargoLoaders = cargoLoaders
           )

          val publicNumber =
           response.optString("public_number")

          orderPublicNumber =
           publicNumber.ifBlank {
            response.optString("id")
           }

          orderCreated = true
         }
        } catch (error: Exception) {
         orderError = error.message
          ?: "Не удалось выполнить запрос. Попробуйте ещё раз."
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
         pricePreview != null &&
                 pricePreviewSignature ==
                 currentPricePreviewSignature ->
          "Подтвердить и заказать"
         else -> "Рассчитать стоимость"
        },
        color = Color.White,
        fontSize = 16.sp
       )
      }
     }

     Text(
      "VEXA такси.",
      color = Color.Gray,
      fontSize = 10.sp
     )
    }
   }
  }

  if (showPassengerAuthDialog) {
   PassengerAuthDialog(
    onAuthenticated = {
     showPassengerAuthDialog = false
    },
    onDismiss = {
     showPassengerAuthDialog = false
    }
   )
  }
 }
}
