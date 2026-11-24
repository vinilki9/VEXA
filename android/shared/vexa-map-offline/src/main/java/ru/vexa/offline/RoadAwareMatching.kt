package ru.vexa.offline

import kotlin.math.*

/** Road metadata must come from a verified routing graph, never inferred from GPS altitude. */
data class RoadEdge(
    val id: String,
    val points: List<NavPoint>,
    val layer: Int? = null,
    val bearingDegrees: Double? = null,
    val accessibleByCar: Boolean = true
)
data class RoadMatch(
    val edgeId: String,
    val projection: RouteProjection,
    val score: Double,
    val confident: Boolean,
    val ambiguous: Boolean
)

/** Candidate scoring for parallel roads / interchanges. Does not determine lanes or legal access. */
object RoadAwareMatcher {
    private fun angularDifference(a: Double, b: Double): Double =
        abs(((a - b + 540.0) % 360.0) - 180.0)

    fun match(
        fix: NavPoint,
        accuracyMeters: Double,
        edges: List<RoadEdge>,
        headingDegrees: Double? = null,
        previousEdgeId: String? = null,
        expectedLayer: Int? = null
    ): RoadMatch? {
        if (!accuracyMeters.isFinite() || accuracyMeters !in 0.0..100.0) return null
        val ranked = edges.asSequence().filter { it.accessibleByCar && it.points.size >= 2 }
            .mapNotNull { edge ->
                val projected = RouteMatcher.project(fix, edge.points) ?: return@mapNotNull null
                if (projected.deviationMeters > max(50.0, accuracyMeters * 3.0)) return@mapNotNull null
                val headingPenalty = if (headingDegrees != null && headingDegrees.isFinite() &&
                    edge.bearingDegrees != null && edge.bearingDegrees.isFinite())
                    angularDifference(headingDegrees, edge.bearingDegrees) / 180.0 * 45.0 else 0.0
                // An explicit level mismatch is strongly discouraged, but GPS altitude is not trusted.
                val layerPenalty = if (expectedLayer != null && edge.layer != null && expectedLayer != edge.layer)
                    35.0 else 0.0
                val continuityBonus = if (previousEdgeId != null && previousEdgeId == edge.id) 12.0 else 0.0
                Triple(edge, projected, projected.deviationMeters + headingPenalty + layerPenalty - continuityBonus)
            }.sortedBy { it.third }.toList()
        val best = ranked.firstOrNull() ?: return null
        val runnerUp = ranked.getOrNull(1)
        val ambiguous = runnerUp != null && runnerUp.third - best.third < max(8.0, accuracyMeters * 0.6)
        val confident = !ambiguous && best.second.deviationMeters <= max(15.0, accuracyMeters * 1.5)
        return RoadMatch(best.first.id, best.second, best.third, confident, ambiguous)
    }
}

/** Emits spoken instructions only on threshold crossing; call with remaining distance decreasing. */
data class Maneuver(val id: String, val instruction: String, val distanceMeters: Double)
class VoicePromptGate {
    private val emitted = mutableSetOf<String>()
    fun next(maneuver: Maneuver, speedMetersPerSecond: Double): String? {
        if (!maneuver.distanceMeters.isFinite() || maneuver.distanceMeters < 0 ||
            !speedMetersPerSecond.isFinite() || speedMetersPerSecond < 0) return null
        val threshold = (speedMetersPerSecond * 12.0).coerceIn(45.0, 350.0)
        val key = maneuver.id + ":approach"
        if (maneuver.distanceMeters <= threshold && emitted.add(key)) return maneuver.instruction
        return null
    }
    fun reset() = emitted.clear()
}
