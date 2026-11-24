package ru.vexa.driver

/** Чистая функция: одно оповещение на ID предложения, без повторов при каждом опросе. */
internal object DriverOfferAlertPolicy {
    fun newOfferId(lastAlertedId: String?, offerIds: List<String>): String? {
        val first = offerIds.firstOrNull { it.isNotBlank() } ?: return null
        return first.takeUnless { it == lastAlertedId }
    }
}
