package ru.vexa.offline

import kotlin.math.*

/** Geometry-only display helper. Not a turn-by-turn maneuver or legal road validator. */
data class RouteProgress(
    val remainingMeters: Double,
    val traveledMeters: Double,
    val deviationMeters: Double,
    val atDestination: Boolean
)

object RouteProgressEstimator {
    /** Reject inaccurate fixes and off-route points to avoid misleading arrival announcements. */
    fun estimate(position: NavPoint, accuracyMeters: Double, route: List<NavPoint>): RouteProgress? {
        if (!accuracyMeters.isFinite() || accuracyMeters !in 0.0..25.0 || route.size < 2) return null
        val projection = RouteMatcher.project(position, route) ?: return null
        if (projection.deviationMeters > max(25.0, 2.0 * accuracyMeters)) return null
        var total = 0.0
        var traveled = 0.0
        for (index in 0 until route.lastIndex) {
            val segment = distanceMeters(route[index], route[index + 1])
            if (!segment.isFinite()) return null
            total += segment
            if (index < projection.segmentIndex) traveled += segment
            if (index == projection.segmentIndex) traveled += segment * projection.fraction
        }
        val remaining = (total - traveled).coerceAtLeast(0.0)
        // The vehicle must be near the actual route end, not merely projected onto its final segment.
        val arrival = remaining <= 30.0 && distanceMeters(position, route.last()) <= 40.0
        return RouteProgress(remaining, traveled, projection.deviationMeters, arrival)
    }
}

/** Announces approach only once per route; rejects GPS jumps and duplicate callbacks. */
class ArrivalAnnouncement(private val thresholdMeters: Double = 250.0) {
    private var saidApproach = false
    private var saidArrival = false
    fun message(progress: RouteProgress?): String? {
        if (progress == null) return null
        if (progress.atDestination) {
            if (saidArrival) return null
            saidArrival = true
            return "Вы прибыли к месту назначения"
        }
        if (progress.remainingMeters <= thresholdMeters && !saidApproach) {
            saidApproach = true
            return "Через ${thresholdMeters.toInt()} метров прибытие к месту назначения"
        }
        return null
    }
    fun reset() { saidApproach = false; saidArrival = false }
}
