package ru.vexa.offline

import kotlin.math.*

/** Geometric route projection. Not a road-graph / lane-level map matcher. */
data class RouteProjection(val point: NavPoint, val deviationMeters: Double,
    val segmentIndex: Int, val fraction: Double)

object RouteMatcher {
    fun project(fix: NavPoint, route: List<NavPoint>): RouteProjection? {
        if (route.size < 2 || !fix.latitude.isFinite() || !fix.longitude.isFinite() ||
            fix.latitude !in -90.0..90.0 || fix.longitude !in -180.0..180.0) return null
        val latScale = 111195.0
        val lonScale = latScale * cos(Math.toRadians(fix.latitude))
        if (abs(lonScale) < 1.0) return null
        var best: RouteProjection? = null
        for (i in 0 until route.lastIndex) {
            val a = route[i]; val b = route[i + 1]
            if (!a.latitude.isFinite() || !a.longitude.isFinite() || !b.latitude.isFinite() || !b.longitude.isFinite() ||
                a.latitude !in -90.0..90.0 || b.latitude !in -90.0..90.0 ||
                a.longitude !in -180.0..180.0 || b.longitude !in -180.0..180.0) continue
            val ax = (a.longitude - fix.longitude) * lonScale
            val ay = (a.latitude - fix.latitude) * latScale
            val dx = (b.longitude - a.longitude) * lonScale
            val dy = (b.latitude - a.latitude) * latScale
            val lengthSq = dx * dx + dy * dy
            val t = if (lengthSq < 0.000001) 0.0 else (-(ax * dx + ay * dy) / lengthSq).coerceIn(0.0, 1.0)
            val d = hypot(ax + t * dx, ay + t * dy)
            if (d.isFinite() && (best == null || d < best.deviationMeters)) {
                best = RouteProjection(NavPoint(a.latitude + t * (b.latitude - a.latitude),
                    a.longitude + t * (b.longitude - a.longitude)), d, i, t)
            }
        }
        return best
    }
}

/** Candidate selection is never proof of a legal stopping place. */
object PickupSafety {
    fun bestVerified(candidates: List<PickupCandidate>): PickupCandidate? =
        SmartPickupRanker.rank(candidates).firstOrNull()
}
