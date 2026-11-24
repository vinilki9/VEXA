package ru.vexa.offline

import java.util.PriorityQueue
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt

/** Read-only, bounded road-graph search. No straight-line route substitution. */
data class OfflineNode(val id: Long, val latitude: Double, val longitude: Double)
data class OfflineEdge(val from: Long, val to: Long, val meters: Double, val seconds: Double)
/** A restriction applies to two consecutive directed arcs through a via node. */
data class OfflineTurnRestriction(val from: Long, val via: Long, val to: Long)
data class OfflineRoute(val points: List<OfflineNode>, val meters: Double, val seconds: Double,
                        val sourceRegion: String, val startSnapMeters: Double, val endSnapMeters: Double)

object OfflineGraph {
    fun distanceMeters(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val p1 = Math.toRadians(lat1)
        val p2 = Math.toRadians(lat2)
        val dLat = p2 - p1
        val dLon = Math.toRadians(lon2 - lon1)
        val a = sin(dLat / 2).pow(2) + cos(p1) * cos(p2) * sin(dLon / 2).pow(2)
        return 6371000.0 * 2 * asin(min(1.0, sqrt(a.coerceIn(0.0, 1.0))))
    }

    fun findRoute(nodes: List<OfflineNode>, edges: List<OfflineEdge>,
                  startLat: Double, startLon: Double, endLat: Double, endLon: Double,
                  region: String, maxSnapMeters: Double = 350.0,
                  forbiddenTurns: Set<OfflineTurnRestriction> = emptySet()): OfflineRoute? {
        if (nodes.isEmpty() || edges.isEmpty() || !listOf(startLat, startLon, endLat, endLon).all { it.isFinite() }) return null
        val nearestStart = nodes.minByOrNull { distanceMeters(startLat, startLon, it.latitude, it.longitude) } ?: return null
        val nearestEnd = nodes.minByOrNull { distanceMeters(endLat, endLon, it.latitude, it.longitude) } ?: return null
        val snapStart = distanceMeters(startLat, startLon, nearestStart.latitude, nearestStart.longitude)
        val snapEnd = distanceMeters(endLat, endLon, nearestEnd.latitude, nearestEnd.longitude)
        if (snapStart > maxSnapMeters || snapEnd > maxSnapMeters) return null
        val vertices = nodes.associateBy { it.id }
        val adjacency = HashMap<Long, MutableList<OfflineEdge>>()
        edges.forEach { e ->
            if (vertices.containsKey(e.from) && vertices.containsKey(e.to) &&
                e.meters.isFinite() && e.seconds.isFinite() && e.meters > 0 && e.seconds > 0) {
                adjacency.getOrPut(e.from) { mutableListOf() }.add(e)
            }
        }
        // State includes the preceding node; node-only Dijkstra can violate turn restrictions.
        data class State(val previous: Long?, val current: Long)
        val start = State(null, nearestStart.id)
        val best = HashMap<State, Double>()
        val parents = HashMap<State, Pair<State, OfflineEdge>>()
        val queue = PriorityQueue(compareBy<Pair<Double, State>> { it.first })
        best[start] = 0.0
        queue.add(0.0 to start)
        var goal: State? = null
        while (queue.isNotEmpty()) {
            val (cost, state) = queue.remove()
            if (cost > (best[state] ?: Double.POSITIVE_INFINITY)) continue
            if (state.current == nearestEnd.id) { goal = state; break }
            for (edge in adjacency[state.current].orEmpty()) {
                if (state.previous != null && OfflineTurnRestriction(
                        state.previous, state.current, edge.to) in forbiddenTurns) continue
                val nextState = State(state.current, edge.to)
                val nextCost = cost + edge.seconds
                if (nextCost < (best[nextState] ?: Double.POSITIVE_INFINITY)) {
                    best[nextState] = nextCost
                    parents[nextState] = state to edge
                    queue.add(nextCost to nextState)
                }
            }
        }
        var state = goal ?: return null
        val reverse = mutableListOf(vertices[state.current] ?: return null)
        var meters = 0.0
        var steps = 0
        while (state != start) {
            val (parent, edge) = parents[state] ?: return null
            meters += edge.meters
            state = parent
            reverse.add(vertices[state.current] ?: return null)
            if (++steps > parents.size + 1) return null
        }
        return OfflineRoute(reverse.asReversed(), meters, best[goal]!!,
            region, snapStart, snapEnd)
    }
}
