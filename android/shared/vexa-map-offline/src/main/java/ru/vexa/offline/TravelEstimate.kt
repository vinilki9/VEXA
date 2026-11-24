package ru.vexa.offline

import kotlin.math.ceil

/** Estimated remaining travel time from recent GPS speed, NOT traffic ETA. */
data class TravelEstimate(val remainingMeters: Double, val approximateMinutes: Int)

object TravelEstimateCalculator {
    fun estimate(progress: RouteProgress?, speedKmh: Int?): TravelEstimate? {
        if (progress == null || speedKmh == null || speedKmh !in 5..130 ||
            !progress.remainingMeters.isFinite() || progress.remainingMeters < 0) return null
        // This is a rough instantaneous estimate, not turn penalties, traffic or arrival promises.
        val minutes = ceil(progress.remainingMeters / (speedKmh / 3.6) / 60.0).toInt()
        return TravelEstimate(progress.remainingMeters, minutes.coerceAtMost(999))
    }
}
