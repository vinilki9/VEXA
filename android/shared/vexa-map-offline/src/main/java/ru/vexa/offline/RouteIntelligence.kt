package ru.vexa.offline

import kotlin.math.*

/** Navigation primitives: no trace persistence, no network access. */
data class NavPoint(val latitude: Double, val longitude: Double)
data class NavFix(val point: NavPoint, val accuracyMeters: Double, val elapsedMs: Long)
data class NavResult(val point: NavPoint?, val accepted: Boolean, val reason: String)

fun distanceMeters(a: NavPoint, b: NavPoint): Double {
    val lat = Math.toRadians(b.latitude - a.latitude)
    val lon = Math.toRadians(b.longitude - a.longitude)
    val h = sin(lat / 2).pow(2) + cos(Math.toRadians(a.latitude)) *
        cos(Math.toRadians(b.latitude)) * sin(lon / 2).pow(2)
    return 6371000.0 * 2 * atan2(sqrt(h.coerceIn(0.0, 1.0)), sqrt((1 - h).coerceIn(0.0, 1.0)))
}

class GpsSmoother {
    private var last: NavFix? = null
    private var filtered: NavPoint? = null
    fun update(fix: NavFix): NavResult {
        val p = fix.point
        if (!p.latitude.isFinite() || !p.longitude.isFinite() ||
            p.latitude !in -90.0..90.0 || p.longitude !in -180.0..180.0 ||
            !fix.accuracyMeters.isFinite() || fix.accuracyMeters !in 0.0..75.0)
            return NavResult(filtered, false, "accuracy")
        val prev = last
        if (prev != null) {
            val dt = (fix.elapsedMs - prev.elapsedMs) / 1000.0
            if (dt <= 0) return NavResult(filtered, false, "timestamp")
            if (distanceMeters(prev.point, p) > 65.0 * dt + max(prev.accuracyMeters, fix.accuracyMeters) * 1.5)
                return NavResult(filtered, false, "jump")
        }
        val alpha = if (filtered == null) 1.0 else if (fix.accuracyMeters <= 8) 0.65 else if (fix.accuracyMeters <= 20) 0.4 else 0.22
        val old = filtered
        val next = if (old == null) p else NavPoint(old.latitude + alpha * (p.latitude - old.latitude),
            old.longitude + alpha * (p.longitude - old.longitude))
        last = fix
        filtered = next
        return NavResult(next, true, "ok")
    }
    fun reset() { last = null; filtered = null }
}

/** Must receive stopping permissions from verified road data; never infers legality. */
data class PickupCandidate(val id: String, val point: NavPoint, val walkMeters: Double,
    val detourMeters: Double, val legalStop: Boolean, val accessible: Boolean)
object SmartPickupRanker {
    fun rank(items: List<PickupCandidate>): List<PickupCandidate> = items
        .filter { it.legalStop && it.accessible && it.walkMeters >= 0 && it.detourMeters >= 0 }
        .sortedWith(compareBy<PickupCandidate> { it.walkMeters + 0.35 * it.detourMeters }.thenBy { it.id })
}

/** A single GPS outlier never triggers rerouting. */
class RerouteGate(private val thresholdMeters: Double = 35.0,
    private val requiredFixes: Int = 3, private val cooldownMs: Long = 8000L) {
    private var count = 0
    private var lastTrigger: Long? = null
    fun observe(offRouteMeters: Double, elapsedMs: Long, accurate: Boolean): Boolean {
        if (!accurate || !offRouteMeters.isFinite() || offRouteMeters < thresholdMeters) {
            count = 0
            return false
        }
        count++
        if (count < requiredFixes || (lastTrigger != null && elapsedMs - lastTrigger!! < cooldownMs)) return false
        lastTrigger = elapsedMs
        count = 0
        return true
    }
    fun reset() { count = 0; lastTrigger = null }
}


/** Closest distance to a polyline segment in a local tangent-plane approximation.
 * Suitable for short segments; a routing engine remains authoritative for road matching. */
object RouteGeometry {
    fun deviationMeters(position: NavPoint, route: List<NavPoint>): Double? {
        if (route.size < 2 || !position.latitude.isFinite() || !position.longitude.isFinite()) return null
        val latScale = 111_195.0
        val lonScale = latScale * cos(Math.toRadians(position.latitude))
        fun xy(p: NavPoint): Pair<Double, Double> =
            Pair((p.longitude - position.longitude) * lonScale, (p.latitude - position.latitude) * latScale)
        var nearest = Double.POSITIVE_INFINITY
        for (i in 0 until route.lastIndex) {
            val (ax, ay) = xy(route[i]); val (bx, by) = xy(route[i + 1])
            if (!ax.isFinite() || !ay.isFinite() || !bx.isFinite() || !by.isFinite()) continue
            val dx = bx - ax; val dy = by - ay
            val t = if (dx * dx + dy * dy < 0.000001) 0.0 else
                (-(ax * dx + ay * dy) / (dx * dx + dy)).coerceIn(0.0, 1.0)
            nearest = min(nearest, hypot(ax + t * dx, ay + t * dy))
        }
        return nearest.takeIf { it.isFinite() }
    }
}

/** Interpolate shortest heading arc; prevents 359° -> 0° camera spins. */
object CameraMotion {
    fun bearing(fromDegrees: Double, toDegrees: Double, fraction: Double): Double {
        if (!fromDegrees.isFinite() || !toDegrees.isFinite()) return 0.0
        val delta = ((toDegrees - fromDegrees + 540.0) % 360.0) - 180.0
        return ((fromDegrees + delta * fraction.coerceIn(0.0, 1.0)) % 360.0 + 360.0) % 360.0
    }
    fun zoomForSpeed(speedMetersPerSecond: Double, threeD: Boolean): Double {
        val speed = speedMetersPerSecond.coerceIn(0.0, 40.0)
        return (if (threeD) 16.8 else 16.2) - 1.5 * speed / 40.0
    }
}
