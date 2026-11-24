package ru.vexa.offline

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.IOException
import kotlin.math.max
import kotlin.math.min

/** Optional VEXA v1 navigation extension tables inside installed raster MBTiles. */
data class OfflinePlace(val name: String, val latitude: Double, val longitude: Double,
                        val region: String, val rank: Int)
data class OfflineNavigationStatus(val addressRegions: Set<String>, val routingRegions: Set<String>)

class OfflineNavigation(context: Context) {
    private val root = File(context.applicationContext.filesDir, "vexa-map/offline")

    private fun installedFiles(): List<Pair<String, File>> = OfflineMapRules.districts.keys.mapNotNull { region ->
        val file = File(root, "$region.mbtiles")
        val marker = File(root, "$region.installed.json")
        val ok = runCatching {
            val meta = JSONObject(marker.readText())
            meta.optString("region_id") == region &&
                OfflineMapRules.validDigest(meta.optString("sha256")) &&
                meta.optLong("size_bytes", -1) == file.length() && file.length() > 0L
        }.getOrDefault(false)
        if (ok && file.isFile) region to file else null
    }

    private fun <T> withRegion(file: File, region: String, block: (SQLiteDatabase) -> T): T? = try {
        SQLiteDatabase.openDatabase(file.absolutePath, null,
            SQLiteDatabase.OPEN_READONLY or SQLiteDatabase.NO_LOCALIZED_COLLATORS).use { db ->
            val values = HashMap<String, String>()
            db.rawQuery("SELECT name, value FROM metadata WHERE name IN ('vexa_navigation_schema','vexa_region_id')", null).use {
                while (it.moveToNext()) values[it.getString(0)] = it.getString(1)
            }
            if (values["vexa_navigation_schema"] != "v1" || values["vexa_region_id"] != region) null
            else block(db)
        }
    } catch (tooLarge: IOException) {
        throw tooLarge
    } catch (_: Exception) {
        null // missing navigation tables, malformed package, etc.
    }

    suspend fun status(): OfflineNavigationStatus = withContext(Dispatchers.IO) {
        val addresses = mutableSetOf<String>()
        val routing = mutableSetOf<String>()
        installedFiles().forEach { (region, file) ->
            withRegion(file, region) { db ->
                db.rawQuery("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('vexa_places','vexa_terms','vexa_nodes','vexa_edges')", null).use { cursor ->
                    val tables = mutableSetOf<String>()
                    while (cursor.moveToNext()) tables.add(cursor.getString(0))
                    if (tables.containsAll(setOf("vexa_places", "vexa_terms"))) addresses.add(region)
                    if (tables.containsAll(setOf("vexa_nodes", "vexa_edges"))) routing.add(region)
                }
            }
        }
        OfflineNavigationStatus(addresses, routing)
    }

    /** Nearby directed road edges from an installed v1 graph. No invented layer/legality metadata. */
    suspend fun nearbyRoadEdges(latitude: Double, longitude: Double, radiusMeters: Double = 120.0,
                                limit: Int = 160): List<RoadEdge> = withContext(Dispatchers.IO) {
        if (!latitude.isFinite() || !longitude.isFinite() || latitude !in -90.0..90.0 ||
            longitude !in -180.0..180.0 || radiusMeters !in 10.0..250.0) return@withContext emptyList()
        val latDelta = radiusMeters / 111_195.0
        val lonDelta = radiusMeters / (111_195.0 * kotlin.math.cos(Math.toRadians(latitude))
            .coerceAtLeast(0.05))
        val result = ArrayList<RoadEdge>()
        for ((region, file) in installedFiles()) {
            if (result.size >= limit) break
            withRegion(file, region) { db ->
                val rowsLimit = (limit - result.size).coerceIn(1, 200)
                // The v1 schema stores directed source/target edges. Direction is preserved.
                db.rawQuery("SELECT e.source_id,e.target_id,a.latitude,a.longitude,b.latitude,b.longitude " +
                    "FROM vexa_edges e JOIN vexa_nodes a ON a.node_id=e.source_id " +
                    "JOIN vexa_nodes b ON b.node_id=e.target_id " +
                    "WHERE a.latitude BETWEEN ? AND ? AND a.longitude BETWEEN ? AND ? " +
                    "AND b.latitude BETWEEN ? AND ? AND b.longitude BETWEEN ? AND ? LIMIT $rowsLimit",
                    arrayOf((latitude-latDelta).toString(), (latitude+latDelta).toString(),
                        (longitude-lonDelta).toString(), (longitude+lonDelta).toString(),
                        (latitude-latDelta).toString(), (latitude+latDelta).toString(),
                        (longitude-lonDelta).toString(), (longitude+lonDelta).toString())).use { rows ->
                    while (rows.moveToNext()) {
                        val a = NavPoint(rows.getDouble(2), rows.getDouble(3))
                        val b = NavPoint(rows.getDouble(4), rows.getDouble(5))
                        val projection = RouteMatcher.project(NavPoint(latitude, longitude), listOf(a,b))
                        if (projection != null && projection.deviationMeters <= radiusMeters) {
                            val y = Math.toRadians(b.longitude - a.longitude) * kotlin.math.cos(Math.toRadians(b.latitude))
                            val x = Math.toRadians(b.latitude - a.latitude)
                            val bearing = (Math.toDegrees(kotlin.math.atan2(y, x)) + 360.0) % 360.0
                            result.add(RoadEdge("$region:${rows.getLong(0)}:${rows.getLong(1)}",
                                listOf(a,b), bearingDegrees=bearing))
                        }
                    }
                }
            }
        }
        result
    }

    /** Search using pre-normalised prefix tokens; no full-db scan or network request. */
    suspend fun search(query: String, limit: Int = 15): List<OfflinePlace> = withContext(Dispatchers.IO) {
        val tokens = OfflineSearchTerms.tokens(query)
        val lead = tokens.maxByOrNull { it.length } ?: ""
        if (tokens.isEmpty()) return@withContext emptyList()
        val result = mutableListOf<OfflinePlace>()
        for ((region, file) in installedFiles()) {
            withRegion(file, region) { db ->
                db.rawQuery("SELECT DISTINCT p.name,p.latitude,p.longitude,p.rank FROM vexa_terms t " +
                    "JOIN vexa_places p ON p.place_id=t.place_id " +
                    "WHERE t.term >= ? AND t.term < ? ORDER BY p.rank DESC LIMIT 250",
                    arrayOf(lead, lead + "\uffff")).use { rows ->
                    while (rows.moveToNext()) {
                        val name = rows.getString(0)
                        val words = OfflineSearchTerms.tokens(name)
                        if (!tokens.all { t -> words.any { it.startsWith(t) } }) continue
                        val lat = rows.getDouble(1)
                        val lon = rows.getDouble(2)
                        if (lat in -90.0..90.0 && lon in -180.0..180.0) {
                            result.add(OfflinePlace(name, lat, lon, region, rows.getInt(3)))
                        }
                    }
                }
            }
        }
        result.distinctBy { Triple(it.name, it.latitude, it.longitude) }
            .sortedWith(compareByDescending<OfflinePlace> { it.rank }.thenBy { it.name })
            .take(limit.coerceIn(1, 30))
    }

    /** Bounded corridor graph load. Not a full-country navigation engine or guidance system. */
    suspend fun route(startLat: Double, startLon: Double, endLat: Double, endLon: Double): OfflineRoute =
        withContext(Dispatchers.IO) {
            require(startLat in -90.0..90.0 && endLat in -90.0..90.0 &&
                    startLon in -180.0..180.0 && endLon in -180.0..180.0) { "Некорректные координаты" }
            if (OfflineGraph.distanceMeters(startLat, startLon, endLat, endLon) > 90_000) {
                throw IOException("Офлайн-маршруты пока ограничены 90 км. Для дальних поездок используйте онлайн-навигацию.")
            }
            val latPad = max(0.04, kotlin.math.abs(endLat - startLat) * 0.35)
            val lonPad = max(0.05, kotlin.math.abs(endLon - startLon) * 0.35)
            val south = min(startLat, endLat) - latPad
            val north = max(startLat, endLat) + latPad
            val west = min(startLon, endLon) - lonPad
            val east = max(startLon, endLon) + lonPad
            val lastError = "Для этого участка нет локального дорожного графа"
            for ((region, file) in installedFiles()) {
                val result = withRegion(file, region) { db ->
                    val nodes = ArrayList<OfflineNode>()
                    // RTree narrows candidates before loading. Legacy v1 packages use the indexed table scan.
                    val hasRtree = db.rawQuery("SELECT 1 FROM sqlite_master WHERE name='vexa_node_rtree' LIMIT 1", null).use { it.moveToFirst() }
                    val nodeSql = if (hasRtree)
                        "SELECT n.node_id,n.latitude,n.longitude FROM vexa_node_rtree r JOIN vexa_nodes n ON n.node_id=r.node_id " +
                        "WHERE r.min_lat<=? AND r.max_lat>=? AND r.min_lon<=? AND r.max_lon>=? LIMIT 60001"
                    else "SELECT node_id,latitude,longitude FROM vexa_nodes " +
                        "WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ? LIMIT 60001"
                    val nodeArgs = if (hasRtree)
                        arrayOf(north.toString(), south.toString(), east.toString(), west.toString())
                    else arrayOf(south.toString(), north.toString(), west.toString(), east.toString())
                    db.rawQuery(nodeSql, nodeArgs).use { rows ->
                        while (rows.moveToNext()) nodes.add(OfflineNode(rows.getLong(0), rows.getDouble(1), rows.getDouble(2)))
                    }
                    if (nodes.size > 60_000) throw IOException("Слишком большой граф для мобильного поиска; нужен компактный навигационный индекс")
                    if (nodes.size < 2) return@withRegion null
                    val edges = ArrayList<OfflineEdge>()
                    db.rawQuery("SELECT e.source_id,e.target_id,e.distance_m,e.duration_s FROM vexa_edges e " +
                        "JOIN vexa_nodes n ON n.node_id=e.source_id WHERE n.latitude BETWEEN ? AND ? " +
                        "AND n.longitude BETWEEN ? AND ? LIMIT 240001",
                        arrayOf(south.toString(), north.toString(), west.toString(), east.toString())).use { rows ->
                        while (rows.moveToNext()) edges.add(OfflineEdge(rows.getLong(0), rows.getLong(1), rows.getDouble(2), rows.getDouble(3)))
                    }
                    if (edges.size > 240_000) throw IOException("Слишком большой граф для мобильного поиска")
                    OfflineGraph.findRoute(nodes, edges, startLat, startLon, endLat, endLon, region)
                }
                if (result != null) return@withContext result
            }
            throw IOException(lastError + ". В настройках скачайте округ с адресами и дорогами.")
        }
}

