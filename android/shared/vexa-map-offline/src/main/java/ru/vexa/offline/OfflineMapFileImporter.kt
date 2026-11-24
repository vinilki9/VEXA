package ru.vexa.offline

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.net.Uri
import android.provider.OpenableColumns
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest
import kotlin.coroutines.coroutineContext

/** Installs a user-provided genuine MBTiles package; no background network calls or hardcoded tiles. */
data class LocalMapImport(val regionId: String, val format: String, val sizeBytes: Long, val digest: String)

class OfflineMapFileImporter(private val context: Context) {
    private val root = File(context.applicationContext.filesDir, "vexa-map/offline").apply { mkdirs() }

    suspend fun install(regionId: String, uri: Uri, onProgress: suspend (Long) -> Unit = {}): LocalMapImport =
        withContext(Dispatchers.IO) {
            require(OfflineMapRules.validRegion(regionId)) { "Неизвестный федеральный округ" }
            val resolver = context.contentResolver
            var reportedSize = -1L
            resolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { c ->
                if (c.moveToFirst() && !c.isNull(0)) reportedSize = c.getLong(0)
            }
            val limit = 256L * 1024 * 1024 * 1024
            if (reportedSize > limit) throw IOException("Файл превышает лимит 256 ГБ")
            if (reportedSize > 0 && root.usableSpace < reportedSize + 50L * 1024 * 1024)
                throw IOException("Недостаточно места в памяти телефона")
            val temp = File.createTempFile("$regionId-import-", ".tmp", root)
            try {
                val digest = MessageDigest.getInstance("SHA-256")
                var written = 0L
                resolver.openInputStream(uri)?.use { input ->
                    FileOutputStream(temp).use { output ->
                        val buffer = ByteArray(256 * 1024)
                        while (true) {
                            coroutineContext.ensureActive()
                            val n = input.read(buffer)
                            if (n < 0) break
                            written += n
                            if (written > limit) throw IOException("Файл превышает лимит 256 ГБ")
                            if (root.usableSpace < 20L * 1024 * 1024)
                                throw IOException("На телефоне закончилось свободное место")
                            digest.update(buffer, 0, n)
                            output.write(buffer, 0, n)
                            onProgress(written)
                        }
                        output.fd.sync()
                    }
                } ?: throw IOException("Не удалось открыть выбранный файл")
                if (reportedSize > 0 && reportedSize != written)
                    throw IOException("Размер файла не совпал с заявленным")
                if (written == 0L) throw IOException("Пустой файл")
                val format = validateMbtiles(temp, regionId)
                val sha = digest.digest().joinToString("") { "%02x".format(it) }
                val target = File(root, "$regionId.mbtiles")
                // Replace only after the entire new package has been copied and validated.
                Files.move(temp.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING)
                val meta = JSONObject().put("region_id", regionId)
                    .put("data_version", "local-${sha.take(12)}")
                    .put("sha256", sha).put("size_bytes", written)
                val pending = File(root, "$regionId.installed.json.pending")
                pending.writeText(meta.toString())
                Files.move(pending.toPath(), File(root, "$regionId.installed.json").toPath(),
                    StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
                LocalMapImport(regionId, format, written, sha)
            } finally { temp.delete() }
        }

    private fun validateMbtiles(file: File, regionId: String): String {
        // SQLiteDatabase is read-only; source bytes are never modified.
        val db = try { SQLiteDatabase.openDatabase(file.absolutePath, null, SQLiteDatabase.OPEN_READONLY) }
            catch (_: Exception) { throw IOException("Выбранный файл не является корректной SQLite MBTiles") }
        return db.use {
            val metadata = mutableMapOf<String, String>()
            try {
                db.rawQuery("SELECT name,value FROM metadata", null).use { c ->
                    while (c.moveToNext()) metadata[c.getString(0)] = c.getString(1)
                }
                db.rawQuery("SELECT 1 FROM tiles LIMIT 1", null).use { c ->
                    if (!c.moveToFirst()) throw IOException("В MBTiles нет тайлов")
                }
            } catch (e: android.database.sqlite.SQLiteException) {
                throw IOException("Отсутствуют таблицы metadata/tiles формата MBTiles", e)
            }
            val declaredRegion = metadata["vexa_region_id"]
            if (!declaredRegion.isNullOrBlank() && declaredRegion != regionId)
                throw IOException("В пакете указан округ $declaredRegion, а выбран $regionId")
            val format = metadata["format"]?.lowercase()?.let { if (it == "jpeg") "jpg" else it }
                ?: throw IOException("В metadata отсутствует format")
            if (format !in setOf("png", "jpg", "webp", "pbf"))
                throw IOException("Формат $format не поддерживается")
            val min = metadata["minzoom"]?.toIntOrNull() ?: 0
            val max = metadata["maxzoom"]?.toIntOrNull() ?: 18
            if (min !in 0..22 || max !in min..22) throw IOException("Недопустимые уровни масштаба")
            if (format == "pbf") {
                val layers = try { JSONObject(metadata["json"] ?: "{}").getJSONArray("vector_layers") }
                    catch (_: Exception) { throw IOException("PBF требует metadata.json.vector_layers") }
                val hasRoads = (0 until layers.length()).any { index ->
                    layers.optJSONObject(index)?.optString("id") in setOf("road", "transportation")
                }
                if (!hasRoads) throw IOException("PBF должен содержать слой road или transportation")
            }
            format
        }
    }
}
