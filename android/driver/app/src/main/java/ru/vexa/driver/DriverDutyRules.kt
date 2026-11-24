package ru.vexa.driver

/** Pure business-side guard used by the driver screen for safe break UX. */
internal object DriverDutyRules {
    private val activeTrip = setOf("assigned", "arrived", "in_progress")
    fun canStartBreak(orderStatuses: List<String>, hasOffer: Boolean): Boolean =
        !hasOffer && orderStatuses.none { it in activeTrip }
}
