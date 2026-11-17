
package ru.vexa.client

import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

object PassengerOrderRepository {

    private const val CITY_CODE = "obolensk"

    private val activeStatuses = setOf(
        "new",
        "accepted",
        "assigned",
        "arrived",
        "in_progress"
    )

    /**
     * Предварительно рассчитать стоимость поездки.
     *
     * Заказ не создаётся.
     * Сервер возвращает стоимость и расшифровку
     * динамического коэффициента.
     */
    suspend fun previewOrderPrice(
        tariffLabel: String,
        customerName: String,
        anonymous: Boolean,
        pickupAddress: String,
        destinationAddress: String,
        pickupLatitude: Double,
        pickupLongitude: Double,
        destinationLatitude: Double,
        destinationLongitude: Double,
        paymentLabel: String,
        childSeat: Boolean,
        animalTransport: Boolean,
        cargoVehicle: String,
        cargoDescription: String,
        cargoLoaders: Int
    ): JSONObject {
        val payload = buildOrderPayload(
            tariffLabel = tariffLabel,
            customerName = customerName,
            anonymous = anonymous,
            pickupAddress = pickupAddress,
            destinationAddress = destinationAddress,
            pickupLatitude = pickupLatitude,
            pickupLongitude = pickupLongitude,
            destinationLatitude = destinationLatitude,
            destinationLongitude = destinationLongitude,
            paymentLabel = paymentLabel,
            childSeat = childSeat,
            animalTransport = animalTransport,
            cargoVehicle = cargoVehicle,
            cargoDescription = cargoDescription,
            cargoLoaders = cargoLoaders
        )

        val response = ApiClient.previewOrderPrice(
            json = payload.toString()
        )

        return JSONObject(response)
    }

    /**
     * Создать заказ пассажира через API VEXA.
     *
     * Для создания заказа передаётся токен
     * предварительного расчёта стоимости.
     * Сервер проверяет токен и использует
     * подтверждённую стоимость.
     */
    suspend fun createOrder(
        tariffLabel: String,
        customerName: String,
        anonymous: Boolean,
        pickupAddress: String,
        destinationAddress: String,
        pickupLatitude: Double,
        pickupLongitude: Double,
        destinationLatitude: Double,
        destinationLongitude: Double,
        paymentLabel: String,
        childSeat: Boolean,
        animalTransport: Boolean,
        cargoVehicle: String,
        cargoDescription: String,
        cargoLoaders: Int,
        priceQuoteToken: String,
        idempotencyKey: String = UUID.randomUUID().toString()
    ): JSONObject {

        require(priceQuoteToken.isNotBlank()) {
            "Необходимо заново рассчитать стоимость заказа."
        }

        val payload = buildOrderPayload(
            tariffLabel = tariffLabel,
            customerName = customerName,
            anonymous = anonymous,
            pickupAddress = pickupAddress,
            destinationAddress = destinationAddress,
            pickupLatitude = pickupLatitude,
            pickupLongitude = pickupLongitude,
            destinationLatitude = destinationLatitude,
            destinationLongitude = destinationLongitude,
            paymentLabel = paymentLabel,
            childSeat = childSeat,
            animalTransport = animalTransport,
            cargoVehicle = cargoVehicle,
            cargoDescription = cargoDescription,
            cargoLoaders = cargoLoaders
        )

        payload.put("price_quote_token", priceQuoteToken)

        val response = ApiClient.sendOrder(
            json = payload.toString(),
            idempotencyKey = idempotencyKey
        )

        return JSONObject(response)
    }

    /**
     * Общая подготовка данных заказа.
     *
     * Используется как для предварительного расчёта,
     * так и для фактического оформления поездки.
     */
    private suspend fun buildOrderPayload(
        tariffLabel: String,
        customerName: String,
        anonymous: Boolean,
        pickupAddress: String,
        destinationAddress: String,
        pickupLatitude: Double,
        pickupLongitude: Double,
        destinationLatitude: Double,
        destinationLongitude: Double,
        paymentLabel: String,
        childSeat: Boolean,
        animalTransport: Boolean,
        cargoVehicle: String,
        cargoDescription: String,
        cargoLoaders: Int
    ): JSONObject {

        val phone = ApiClient.getPassengerPhone()
            ?: throw IllegalStateException(
                "Не найден подтверждённый номер телефона. Войдите в профиль."
            )

        if (ApiClient.getAccessToken().isNullOrBlank()) {
            throw IllegalStateException(
                "Необходимо войти в профиль VEXA."
            )
        }

        require(pickupAddress.isNotBlank()) {
            "Укажите адрес подачи."
        }

        require(destinationAddress.isNotBlank()) {
            "Укажите адрес назначения."
        }

        val tariffsResponse = ApiClient.getTariffs(CITY_CODE)
        val tariffsJson = JSONObject(tariffsResponse)
        val tariffs = tariffsJson.optJSONArray("tariffs")
            ?: JSONArray()

        if (tariffs.length() == 0) {
            throw IllegalStateException(
                "В Оболенске пока не настроены активные тарифы."
            )
        }

        val selectedTariff = findTariff(
            tariffs = tariffs,
            tariffLabel = tariffLabel
        )

        val tariffId = selectedTariff.optString("id")

        if (tariffId.isBlank()) {
            throw IllegalStateException(
                "У выбранного тарифа отсутствует идентификатор."
            )
        }

        val normalizedName = customerName.trim()
        val isAnonymous = anonymous || normalizedName.isBlank()

        val paymentMethod = when (paymentLabel.trim()) {
            "Наличные" -> "cash"
            "Перевод водителю" -> "driver_transfer"
            "Банковская карта" -> "card"
            "СБП" -> "sbp"
            else -> throw IllegalArgumentException(
                "Неизвестный способ оплаты: $paymentLabel"
            )
        }

        val cargoOrder = isCargoTariff(selectedTariff)

        return JSONObject().apply {
            put("city_code", CITY_CODE)
            put("tariff_id", tariffId)

            put(
                "customer_name",
                if (isAnonymous) JSONObject.NULL else normalizedName
            )

            put("customer_phone", phone)
            put("anonymous", isAnonymous)

            put("pickup_address", pickupAddress.trim())
            put("destination_address", destinationAddress.trim())

            put("pickup_latitude", pickupLatitude)
            put("pickup_longitude", pickupLongitude)
            put("destination_latitude", destinationLatitude)
            put("destination_longitude", destinationLongitude)

            put("payment_method", paymentMethod)

            put("child_seat", if (cargoOrder) false else childSeat)
            put(
                "animal_transport",
                if (cargoOrder) false else animalTransport
            )

            if (cargoOrder) {
                put("cargo_vehicle", cargoVehicle)
                put(
                    "cargo_description",
                    cargoDescription.trim().ifBlank {
                        JSONObject.NULL
                    }
                )
                put("cargo_loaders", cargoLoaders)
            } else {
                put("cargo_vehicle", JSONObject.NULL)
                put("cargo_description", JSONObject.NULL)
                put("cargo_loaders", 0)
            }
        }
    }

    /**
     * Получить последний заказ пассажира с сервера.
     *
     * Сервер возвращает заказы в порядке от новых к старым.
     * Поэтому первый элемент — последний созданный заказ.
     */
    suspend fun getLatestOrder(): JSONObject? {
        val response = ApiClient.getPassengerOrders()
        val orders = JSONArray(response)

        if (orders.length() == 0) {
            return null
        }

        return orders.optJSONObject(0)
    }

    /**
     * Получить последний активный заказ пассажира.
     *
     * Если активного заказа нет, возвращается null.
     */
    suspend fun getActiveOrder(): JSONObject? {
        val response = ApiClient.getPassengerOrders()
        val orders = JSONArray(response)

        for (index in 0 until orders.length()) {
            val order = orders.optJSONObject(index)
                ?: continue

            val status = order.optString("status")

            if (status in activeStatuses) {
                return order
            }
        }

        return null
    }

    /**
     * Найти тариф по названию или коду,
     * полученным из интерфейса пассажира.
     */
    private fun findTariff(
        tariffs: JSONArray,
        tariffLabel: String
    ): JSONObject {

        val requested = normalize(tariffLabel)

        for (index in 0 until tariffs.length()) {
            val item = tariffs.optJSONObject(index)
                ?: continue

            val name = normalize(item.optString("name"))
            val code = normalize(item.optString("code"))

            if (
                requested == name ||
                requested == code
            ) {
                return item
            }
        }

        if (
            requested.contains("груз") ||
            requested.contains("cargo")
        ) {
            for (index in 0 until tariffs.length()) {
                val item = tariffs.optJSONObject(index)
                    ?: continue

                val name = normalize(item.optString("name"))
                val code = normalize(item.optString("code"))
                val vehicleClass = normalize(
                    item.optString("vehicle_class")
                )

                if (
                    name.contains("груз") ||
                    name.contains("cargo") ||
                    code.contains("cargo") ||
                    vehicleClass.contains("груз") ||
                    vehicleClass.contains("cargo")
                ) {
                    return item
                }
            }
        }

        val available = buildList {
            for (index in 0 until tariffs.length()) {
                val item = tariffs.optJSONObject(index)
                    ?: continue

                add(
                    item.optString("name").ifBlank {
                        item.optString("code")
                    }
                )
            }
        }

        throw IllegalArgumentException(
            "Тариф «$tariffLabel» не найден на сервере. " +
                "Доступные тарифы: ${available.joinToString(", ")}"
        )
    }

    private fun isCargoTariff(
        tariff: JSONObject
    ): Boolean {
        val values = listOf(
            tariff.optString("code"),
            tariff.optString("name"),
            tariff.optString("vehicle_class")
        )

        return values.any {
            val value = normalize(it)
            value.contains("груз") ||
                value.contains("cargo")
        }
    }

    private fun normalize(value: String): String {
        return value.trim()
            .lowercase()
            .replace(" ", "")
            .replace("+", "plus")
            .replace("-", "")
            .replace("_", "")
    }
}
