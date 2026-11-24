package ru.vexa.offline

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.Closeable
import java.io.File
import java.io.IOException
import java.io.InputStreamReader
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketException
import java.net.URLDecoder
import java.nio.charset.StandardCharsets
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/**
 * Read-only localhost renderer adapter for verified, installed MBTiles (raster or vector PBF).
 * PBF requires valid `metadata.json.vector_layers` in the MBTiles file; street labels require
 * locally embedded `vexa_glyphs` ranges. NEVER downloads fonts or tiles from the internet.
 * This local HTTP service is only a map tile/glyph provider, not a geocoder or router.
 */
class OfflineMbtilesServer(context: Context) : Closeable {
    private val root = File(context.applicationContext.filesDir, "vexa-map/offline")
    private data class Pack(
        val id: String, val file: File, val format: String, val attribution: String,
        val minZoom: Int, val maxZoom: Int, val center: Triple<Double, Double, Double>?,
        val layers: Set<String> = emptySet(), val labelsAvailable: Boolean = false
    )
    @Volatile private var packages: List<Pack> = emptyList()
    @Volatile private var listener: ServerSocket? = null
    private var workers: ExecutorService? = null
    private var acceptThread: Thread? = null
    private val guard = Any()

    fun refresh(): Int {
        val list = mutableListOf<Pack>()
        for (id in OfflineMapRules.districts.keys) {
            val file = File(root, "$id.mbtiles")
            val info = File(root, "$id.installed.json")
            if (!file.isFile || !info.isFile) continue
            val valid = runCatching {
                val meta = JSONObject(info.readText())
                meta.optString("region_id") == id &&
                    OfflineMapRules.validDigest(meta.getString("sha256")) &&
                    meta.optLong("size_bytes", -1) == file.length() && file.length() > 0
            }.getOrDefault(false)
            if (!valid) continue
            val pack = runCatching {
                openReadOnly(file).use { db ->
                    val metadata = mutableMapOf<String, String>()
                    db.rawQuery("SELECT name, value FROM metadata", null).use { cursor ->
                        while (cursor.moveToNext()) metadata[cursor.getString(0)] = cursor.getString(1)
                    }
                    val fmt = metadata["format"]?.lowercase()?.let { if (it == "jpeg") "jpg" else it }.orEmpty()
                    if (fmt !in setOf("png", "jpg", "webp", "pbf")) return@use null
                    val min = metadata["minzoom"]?.toIntOrNull()?.coerceIn(0, 22) ?: 0
                    val max = metadata["maxzoom"]?.toIntOrNull()?.coerceIn(0, 22) ?: 18
                    if (min > max) return@use null
                    val center = parseCenter(metadata)
                    if (fmt != "pbf") return@use Pack(id, file, fmt, metadata["attribution"].orEmpty(), min, max, center)
                    // TileJSON layer IDs are authoritative; never assume all vector schemas match.
                    val layerArray = JSONObject(metadata["json"] ?: "{}").optJSONArray("vector_layers")
                        ?: return@use null
                    val layers = mutableSetOf<String>()
                    for (i in 0 until layerArray.length()) {
                        val name = layerArray.optJSONObject(i)?.optString("id").orEmpty()
                        if (name.matches(Regex("[A-Za-z0-9_-]{1,80}"))) layers.add(name)
                    }
                    if (layers.none { it == "road" || it == "transportation" }) return@use null
                    val fonts = runCatching {
                        db.rawQuery("SELECT range_start FROM vexa_glyphs WHERE fontstack=? AND range_start IN (0,256,1024) " +
                            "AND length(pbf) BETWEEN 1 AND 2097152",
                            arrayOf(FONT_STACK)).use { cursor ->
                            val found = mutableSetOf<Int>()
                            while (cursor.moveToNext()) found.add(cursor.getInt(0))
                            found.containsAll(setOf(0, 256, 1024))
                        }
                    }.getOrDefault(false)
                    Pack(id, file, fmt, metadata["attribution"].orEmpty(), min, max, center, layers, fonts)
                }
            }.getOrNull()
            if (pack != null) list.add(pack)
        }
        packages = list
        return list.size
    }

    /** Compatible format-specific query for legacy clients. */
    fun rasterRegionIds(): Set<String> = packages.filter { it.format != "pbf" }.mapTo(mutableSetOf()) { it.id }
    /** Regions with a usable raster or self-contained vector style. */
    fun renderableRegionIds(): Set<String> = packages.mapTo(mutableSetOf()) { it.id }

    fun regionCenter(regionId: String?): Triple<Double, Double, Double>? =
        (packages.firstOrNull { it.id == regionId } ?: packages.firstOrNull())?.center

    fun mapDescription(regionId: String?): String {
        val p = selectPack(regionId) ?: return "Совместимая офлайн-карта не установлена"
        return if (p.format != "pbf") "Растровая карта: ${p.id}. 3D-здания и подписи PBF недоступны."
        else if (p.labelsAvailable) "Векторная PBF: ${p.id}. Подписи улиц из локальных глифов."
        else "Векторная PBF: ${p.id}. Для подписей добавьте локальные глифы Noto Sans Regular."
    }

    private fun selectPack(regionId: String?): Pack? =
        packages.firstOrNull { it.id == regionId } ?: packages.firstOrNull()

    private fun parseCenter(meta: Map<String, String>): Triple<Double, Double, Double>? {
        val parts = meta["center"]?.split(',')?.mapNotNull(String::toDoubleOrNull)
        if (parts != null && parts.size >= 2 && parts[0] in -180.0..180.0 && parts[1] in -85.0..85.0) {
            return Triple(parts[1], parts[0], parts.getOrNull(2)?.coerceIn(0.0, 18.0) ?: 8.0)
        }
        val bounds = meta["bounds"]?.split(',')?.mapNotNull(String::toDoubleOrNull)
        if (bounds != null && bounds.size == 4 && bounds[0] in -180.0..180.0 &&
            bounds[2] in -180.0..180.0 && bounds[1] in -85.0..85.0 && bounds[3] in -85.0..85.0) {
            val east = if (bounds[2] < bounds[0]) bounds[2] + 360.0 else bounds[2]
            return Triple((bounds[1] + bounds[3]) / 2.0, ((bounds[0] + east) / 2 + 540) % 360 - 180, 6.0)
        }
        return null
    }

    fun start(): String = synchronized(guard) {
        if (listener == null) {
            if (packages.isEmpty()) throw IOException("Нет совместимых MBTiles округа")
            val server = ServerSocket(0, 16, InetAddress.getByName("127.0.0.1"))
            listener = server
            workers = Executors.newFixedThreadPool(3) { task ->
                Thread(task, "vexa-map-offline-tile").apply { isDaemon = true }
            }
            acceptThread = Thread({
                while (!server.isClosed) {
                    try {
                        val socket = server.accept()
                        workers?.execute { socket.use { reply(it) } } ?: socket.close()
                    } catch (_: SocketException) { break }
                    catch (_: IOException) { if (server.isClosed) break }
                }
            }, "vexa-map-offline-listener").apply { isDaemon = true; start() }
        }
        "http://127.0.0.1:${listener!!.localPort}"
    }

    /** Self-contained style: all tile and font requests remain on 127.0.0.1. */
    fun styleJson(origin: String, regionId: String?, buildings3d: Boolean): String {
        val pack = selectPack(regionId) ?: throw IOException("Выберите установленный округ")
        return if (pack.format == "pbf") vectorStyleJson(origin, pack, buildings3d)
               else rasterStyleJson(origin)
    }

    /** The existing multi-district raster source is preserved for backwards compatibility. */
    fun rasterStyleJson(origin: String): String {
        val list = packages.filter { it.format != "pbf" }
        require(list.isNotEmpty()) { "Нет растровых пакетов" }
        val credit = list.map { it.attribution }.filter { it.isNotBlank() }.distinct()
            .joinToString(" · ").ifBlank { "Данные VEXA MAP" }
        return JSONObject().put("version", 8).put("name", "VEXA MAP — растровая офлайн")
            .put("sources", JSONObject().put("regions", JSONObject()
                .put("type", "raster").put("tiles", JSONArray().put("$origin/tiles/{z}/{x}/{y}"))
                .put("tileSize", 256).put("minzoom", list.minOf { it.minZoom })
                .put("maxzoom", list.maxOf { it.maxZoom }).put("attribution", credit)))
            .put("layers", JSONArray().put(background()).put(JSONObject()
                .put("id", "raster-regions").put("type", "raster").put("source", "regions"))).toString()
    }

    private fun background(): JSONObject = JSONObject().put("id", "vexa-background")
        .put("type", "background").put("paint", JSONObject().put("background-color", "#151D21"))

    private fun paintLayer(id: String, type: String, src: String, paint: String, minZoom: Int = 0,
                           layout: String? = null): JSONObject = JSONObject()
        .put("id", id).put("type", type).put("source", "district")
        .put("source-layer", src).put("minzoom", minZoom)
        .put("paint", JSONObject(paint)).apply { if (layout != null) put("layout", JSONObject(layout)) }

    private fun vectorStyleJson(origin: String, pack: Pack, buildings3d: Boolean): String {
        val tileUrl = "$origin/vector/${pack.id}/{z}/{x}/{y}.pbf"
        val source = JSONObject().put("district", JSONObject().put("type", "vector")
            .put("tiles", JSONArray().put(tileUrl)).put("minzoom", pack.minZoom)
            .put("maxzoom", pack.maxZoom).put("attribution", pack.attribution))
        val layers = JSONArray().put(background())
        if ("landcover" in pack.layers) layers.put(paintLayer("landcover", "fill", "landcover", """{"fill-color":"#26372F","fill-opacity":0.55}"""))
        if ("landuse" in pack.layers) layers.put(paintLayer("landuse", "fill", "landuse", """{"fill-color":"#23332E","fill-opacity":0.55}"""))
        if ("water" in pack.layers) layers.put(paintLayer("water", "fill", "water", """{"fill-color":"#183E48"}"""))
        val road = listOf("transportation", "road").firstOrNull { it in pack.layers }
        if (road != null) {
            layers.put(paintLayer("road-casing", "line", road,
                """{"line-color":"#0D171A","line-width":["interpolate",["linear"],["zoom"],5,0.4,15,6.0]}""", 5))
            layers.put(paintLayer("roads", "line", road,
                """{"line-color":"#5D797B","line-width":["interpolate",["linear"],["zoom"],5,0.5,15,4.0]}""", 5))
        }
        if ("building" in pack.layers) {
            if (!buildings3d) layers.put(paintLayer("buildings-flat", "fill", "building",
                """{"fill-color":"#35494B","fill-opacity":0.75}""", 13))
            if (buildings3d) layers.put(paintLayer("buildings-3d", "fill-extrusion", "building",
                """{"fill-extrusion-color":"#476467","fill-extrusion-opacity":0.85,"fill-extrusion-height":["max",3,["coalesce",["to-number",["get","render_height"]],["to-number",["get","height"]],9]]}""", 14))
        }
        if (pack.labelsAvailable) {
            val textLayout = """{"text-field":["coalesce",["get","name:ru"],["get","name"],""],"text-font":["Noto Sans Regular"],"text-size":12,"text-max-width":8}"""
            val textPaint = """{"text-color":"#D7E7E6","text-halo-color":"#151D21","text-halo-width":1.5}"""
            if ("transportation_name" in pack.layers) layers.put(paintLayer("street-labels", "symbol", "transportation_name", textPaint, 12, textLayout))
            else if (road != null) layers.put(paintLayer("street-labels", "symbol", road, textPaint, 14, textLayout))
            if ("place" in pack.layers) layers.put(paintLayer("place-labels", "symbol", "place", textPaint, 5, textLayout))
        }
        val style = JSONObject().put("version", 8).put("name", "VEXA MAP — векторная офлайн")
            .put("sources", source).put("layers", layers)
        if (pack.labelsAvailable) style.put("glyphs", "$origin/glyphs/${pack.id}/{fontstack}/{range}.pbf")
        return style.toString()
    }

    private fun openReadOnly(file: File) = SQLiteDatabase.openDatabase(file.absolutePath, null,
        SQLiteDatabase.OPEN_READONLY or SQLiteDatabase.NO_LOCALIZED_COLLATORS)

    private data class Reply(val data: ByteArray, val mime: String, val gzip: Boolean = false)
    private fun readTile(z: Int, x: Long, y: Long, region: String? = null): Reply? {
        val row = OfflineTileMath.tmsRow(z, x, y) ?: return null
        for (pack in packages) {
            if (pack.id != region && region != null) continue
            if ((region == null && pack.format == "pbf") ||
                (region != null && pack.format != "pbf") || z !in pack.minZoom..pack.maxZoom || !pack.file.isFile) continue
            try {
                val bytes = openReadOnly(pack.file).use { db ->
                    db.rawQuery("SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=? LIMIT 1",
                        arrayOf(z.toString(), x.toString(), row.toString())).use { c ->
                        if (c.moveToFirst()) c.getBlob(0) else null
                    }
                }
                if (bytes != null && bytes.isNotEmpty() && bytes.size <= 4 * 1024 * 1024) {
                    val mime = when (pack.format) {
                        "png" -> "image/png"
                        "webp" -> "image/webp"
                        "jpg" -> "image/jpeg"
                        else -> "application/x-protobuf"
                    }
                    return Reply(bytes, mime, pack.format == "pbf" && isGzip(bytes))
                }
            } catch (_: Exception) { /* Broken district must not break other installed regions. */ }
        }
        return null
    }

    private fun readGlyph(regionId: String, start: Int): Reply? {
        val pack = packages.firstOrNull { it.id == regionId && it.format == "pbf" && it.labelsAvailable } ?: return null
        return runCatching {
            openReadOnly(pack.file).use { db ->
                db.rawQuery("SELECT pbf FROM vexa_glyphs WHERE fontstack=? AND range_start=? LIMIT 1",
                    arrayOf(FONT_STACK, start.toString())).use { c ->
                    val b = if (c.moveToFirst()) c.getBlob(0) else null
                    if (b != null && b.isNotEmpty() && b.size <= 2 * 1024 * 1024)
                        Reply(b, "application/x-protobuf", isGzip(b)) else null
                }
            }
        }.getOrNull()
    }

    private fun isGzip(value: ByteArray): Boolean = value.size > 2 &&
        value[0] == 0x1f.toByte() && value[1] == 0x8b.toByte()

    private fun resource(path: String): Reply? {
        OfflineTileMath.safeTilePath(path)?.let { (z, x, y) -> return readTile(z, x, y) }
        val tileParts = Regex("^/vector/([a-z-]+)/([0-9]{1,2})/([0-9]{1,10})/([0-9]{1,10})\\.pbf$")
            .matchEntire(path)?.groupValues
        if (tileParts != null && OfflineMapRules.validRegion(tileParts[1])) {
            val z = tileParts[2].toIntOrNull() ?: return null
            val x = tileParts[3].toLongOrNull() ?: return null
            val y = tileParts[4].toLongOrNull() ?: return null
            return readTile(z, x, y, tileParts[1])
        }
        val glyphParts = Regex("^/glyphs/([a-z-]+)/([^/]{1,100})/([0-9]{1,5})-([0-9]{1,5})\\.pbf$")
            .matchEntire(path)?.groupValues ?: return null
        if (!OfflineMapRules.validRegion(glyphParts[1])) return null
        val fontstack = runCatching { URLDecoder.decode(glyphParts[2], "UTF-8") }.getOrNull()
        if (fontstack != FONT_STACK) return null
        val from = glyphParts[3].toIntOrNull() ?: return null
        val to = glyphParts[4].toIntOrNull() ?: return null
        if (from !in 0..65280 || from % 256 != 0 || to != from + 255) return null
        return readGlyph(glyphParts[1], from)
    }

    private fun reply(socket: Socket) {
        socket.soTimeout = 5_000
        val output = socket.getOutputStream()
        try {
            val input = BufferedReader(InputStreamReader(socket.getInputStream(), StandardCharsets.US_ASCII))
            val first = input.readLine()?.take(512).orEmpty().split(' ')
            var headerBytes = 0
            while (headerBytes < 16_384) {
                val line = input.readLine() ?: break
                headerBytes += line.length + 2
                if (line.isEmpty()) break
            }
            if (first.size < 3 || first[0] != "GET" || headerBytes >= 16_384) {
                respond(output, 400, null); return
            }
            val requested = resource(first[1])
            respond(output, if (requested != null) 200 else 404, requested)
        } catch (_: Exception) { runCatching { respond(output, 500, null) } }
    }

    private fun respond(out: java.io.OutputStream, code: Int, reply: Reply?) {
        val status = when (code) { 200 -> "OK"; 400 -> "Bad Request"; 404 -> "Not Found"; else -> "Error" }
        val body = reply?.data ?: ByteArray(0)
        val header = "HTTP/1.1 $code $status\r\nContent-Type: ${reply?.mime ?: "text/plain"}\r\n" +
            (if (reply?.gzip == true) "Content-Encoding: gzip\r\n" else "") +
            "Content-Length: ${body.size}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n"
        out.write(header.toByteArray(StandardCharsets.US_ASCII))
        out.write(body)
        out.flush()
    }

    override fun close() = synchronized(guard) {
        listener?.close()
        listener = null
        workers?.shutdownNow()
        workers = null
        acceptThread = null
    }

    companion object { private const val FONT_STACK = "Noto Sans Regular" }
}
