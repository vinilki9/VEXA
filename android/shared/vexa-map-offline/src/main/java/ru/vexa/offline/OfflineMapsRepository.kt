package ru.vexa.offline

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import kotlin.coroutines.coroutineContext

/** A verified download on disk is NOT automatically an active MapLibre offline source. */
data class OfflineRegion(
    val id: String,
    val title: String,
    val available: Boolean = false,
    val downloadable: Boolean = false,
    val version: String? = null,
    val bytes: Long = 0L,
    val sha256: String = "",
    val installedVersion: String? = null,
    val installedSha: String? = null,
    val partialBytes: Long = 0L
) {
    val installed: Boolean get() = installedVersion != null
    val updateAvailable: Boolean get() = installed && available && (sha256 != installedSha || version != installedVersion)
}

class OfflineMapsRepository(context: Context, baseUrl: String, allowInsecureHttp: Boolean = false) {
    private val root = File(context.applicationContext.filesDir, "vexa-map/offline").apply { mkdirs() }
    private val normalizedBase = baseUrl.trimEnd('/')
    private val host = requireNotNull(normalizedBase.toHttpUrlOrNull()) { "Некорректный адрес VEXA MAP" }
    private val client = OkHttpClient.Builder()
        .followRedirects(false).followSslRedirects(false)
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(45, TimeUnit.SECONDS)
        .build()

    init {
        require(host.scheme == "https" || (allowInsecureHttp && host.scheme == "http")) {
            "Для загрузок VEXA MAP требуется HTTPS (HTTP допускается только в debug)"
        }
        require(host.username.isEmpty() && host.password.isEmpty() && host.query == null && host.fragment == null)
    }

    private fun url(path: String) = normalizedBase + path
    private fun target(id: String) = File(root, "$id.mbtiles")
    private fun part(id: String) = File(root, "$id.part")
    private fun partMarker(id: String) = File(root, "$id.part.sha256")
    private fun localMeta(id: String) = File(root, "$id.installed.json")
    private fun requireRegion(id: String) { require(OfflineMapRules.validRegion(id)) { "Неизвестный округ" } }

    private fun request(path: String, headers: Map<String, String> = emptyMap()) =
        Request.Builder().url(url(path)).apply { headers.forEach { (k, v) -> header(k, v) } }.get().build()

    private fun localInfo(id: String): Pair<String, String>? {
        val saved = localMeta(id)
        if (!target(id).isFile || !saved.isFile) return null
        return try {
            val obj = JSONObject(saved.readText())
            val digest = obj.getString("sha256")
            val version = obj.getString("data_version")
            val count = obj.getLong("size_bytes")
            if (OfflineMapRules.validDigest(digest) && count == target(id).length() && version.isNotBlank()) {
                version to digest
            } else null
        } catch (_: Exception) { null }
    }

    suspend fun localCatalog(): List<OfflineRegion> = withContext(Dispatchers.IO) {
        OfflineMapRules.districts.map { (id, name) ->
            val installed = localInfo(id)
            OfflineRegion(id, name, installedVersion = installed?.first,
                installedSha = installed?.second, partialBytes = part(id).takeIf { it.isFile }?.length() ?: 0)
        }
    }

    suspend fun refreshCatalog(): List<OfflineRegion> = withContext(Dispatchers.IO) {
        val response = client.newCall(request("/v1/offline/catalog")).execute()
        response.use {
            if (!it.isSuccessful) throw IOException("Каталог VEXA MAP: HTTP ${it.code}")
            val obj = JSONObject(it.body?.string() ?: "")
            if (obj.optString("schema") != "vexa.offline.catalog.v1") throw IOException("Неверная версия каталога")
            val records = mutableMapOf<String, JSONObject>()
            val rows = obj.getJSONArray("regions")
            for (i in 0 until rows.length()) {
                val row = rows.getJSONObject(i)
                val id = row.optString("region_id")
                if (OfflineMapRules.validRegion(id)) records[id] = row
            }
            OfflineMapRules.districts.map { (id, name) ->
                val row = records[id]
                val present = row?.optBoolean("available", false) ?: false
                val sha = if (present) row?.optString("sha256").orEmpty() else ""
                val size = if (present) row?.optLong("size_bytes", 0L) ?: 0 else 0L
                val ok = present && OfflineMapRules.validDigest(sha) && size > 0
                val installed = localInfo(id)
                OfflineRegion(
                    id, name, available = ok,
                    downloadable = ok && row?.has("download_url") == true,
                    version = if (ok) row?.optString("data_version") else null,
                    bytes = if (ok) size else 0,
                    sha256 = if (ok) sha else "",
                    installedVersion = installed?.first,
                    installedSha = installed?.second,
                    partialBytes = part(id).takeIf { f -> f.isFile }?.length() ?: 0
                )
            }
        }
    }

    /** Remote manifest is fetched just before downloading, not trusted from UI state. */
    private fun manifest(id: String): OfflineRegion {
        requireRegion(id)
        val response = client.newCall(request("/v1/offline/regions/$id/manifest")).execute()
        response.use {
            if (!it.isSuccessful) throw IOException("Манифест $id: HTTP ${it.code}")
            val obj = JSONObject(it.body?.string() ?: "")
            if (obj.optString("schema") != "vexa.offline.region.v1" || obj.optString("region_id") != id ||
                obj.optString("file_name") != "$id.mbtiles") throw IOException("Неверный манифест $id")
            val size = obj.optLong("size_bytes", -1)
            val digest = obj.optString("sha256")
            val version = obj.optString("data_version")
            if (size <= 0 || !OfflineMapRules.validDigest(digest) ||
                !Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,63}").matches(version) ||
                obj.optString("format") !in setOf("png", "jpg", "webp", "pbf")) {
                throw IOException("Недопустимый размер, формат, версия или контрольная сумма")
            }
            return OfflineRegion(id, OfflineMapRules.districts.getValue(id), true, true,
                version, size, digest)
        }
    }

    /** Downloads are resumable, verified, and moved to the installed location only after SHA-256 check. */
    suspend fun download(id: String, onProgress: suspend (Long, Long, String) -> Unit): Unit =
        withContext(Dispatchers.IO) {
            requireRegion(id)
            val info = manifest(id)
            val temp = part(id)
            val marker = partMarker(id)
            val oldDigest = marker.takeIf { it.isFile }?.readText()?.trim().orEmpty()
            if (oldDigest != info.sha256 || temp.length() > info.bytes) {
                temp.delete()
                marker.delete()
            }
            marker.writeText(info.sha256)
            val offset = temp.takeIf { it.isFile }?.length() ?: 0L
            val needed = info.bytes - offset
            if (info.bytes > 256L * 1024L * 1024L * 1024L) {
                throw IOException("Один региональный пакет превышает лимит 256 ГБ")
            }
            val reserve = maxOf(50L * 1024L * 1024L, info.bytes / 20)
            if (needed > 0L && root.usableSpace < needed + reserve) {
                throw IOException("Недостаточно свободного места: нужно ещё ${OfflineMapRules.formatBytes(needed + reserve)}")
            }
            if (offset < info.bytes) {
                val headers = if (offset > 0) mapOf(
                    "Range" to "bytes=$offset-", "If-Range" to "\"${info.sha256}\"") else emptyMap()
                val response = client.newCall(request("/v1/offline/regions/$id/download", headers)).execute()
                response.use { r ->
                    if (r.code != 200 && r.code != 206) throw IOException("Загрузка $id: HTTP ${r.code}")
                    val etag = r.header("ETag")
                    if (etag != null && etag != "\"${info.sha256}\"") throw IOException("Версия пакета изменилась")
                    val append = offset > 0 && r.code == 206
                    if (r.code == 206) {
                        val header = r.header("Content-Range").orEmpty()
                        val match = Regex("bytes (\\d+)-(\\d+)/(\\d+)").matchEntire(header)
                        if (match == null || match.groupValues[1].toLong() != offset ||
                            match.groupValues[3].toLong() != info.bytes) {
                            throw IOException("Неверный ответ сервера для докачки")
                        }
                    }
                    r.body?.byteStream()?.use { input ->
                        FileOutputStream(temp, append).use { output ->
                            val buffer = ByteArray(128 * 1024)
                            while (true) {
                                coroutineContext.ensureActive()
                                val n = input.read(buffer)
                                if (n < 0) break
                                output.write(buffer, 0, n)
                                val soFar = temp.length()
                                if (soFar > info.bytes) throw IOException("Пакет превышает заявленный размер")
                                onProgress(soFar, info.bytes, "Загрузка")
                            }
                            output.fd.sync()
                        }
                    } ?: throw IOException("Пустой ответ сервера")
                }
            }
            if (temp.length() != info.bytes) throw IOException("Переданы не все данные. Нажмите «Продолжить»")
            onProgress(info.bytes, info.bytes, "Проверка SHA-256")
            val digest = MessageDigest.getInstance("SHA-256")
            temp.inputStream().buffered().use { stream ->
                val buffer = ByteArray(512 * 1024)
                while (true) {
                    coroutineContext.ensureActive()
                    val n = stream.read(buffer)
                    if (n == -1) break
                    digest.update(buffer, 0, n)
                }
            }
            val actual = digest.digest().joinToString("") { "%02x".format(it) }
            if (actual != info.sha256) {
                temp.delete()
                marker.delete()
                throw IOException("Контрольная сумма не совпала: повреждённая загрузка удалена")
            }
            // Same-directory atomic replace avoids exposing partially written packages.
            Files.move(temp.toPath(), target(id).toPath(),
                StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
            val meta = JSONObject().put("region_id", id).put("data_version", info.version)
                .put("sha256", info.sha256).put("size_bytes", info.bytes)
            val pending = File(root, "$id.installed.json.tmp")
            pending.writeText(meta.toString())
            Files.move(pending.toPath(), localMeta(id).toPath(),
                StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
            marker.delete()
        }

    suspend fun verifyInstalled(id: String): Boolean = withContext(Dispatchers.IO) {
        requireRegion(id)
        val saved = localInfo(id) ?: return@withContext false
        val digest = MessageDigest.getInstance("SHA-256")
        target(id).inputStream().buffered().use { file ->
            val buffer = ByteArray(512 * 1024)
            while (true) {
                coroutineContext.ensureActive()
                val count = file.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        digest.digest().joinToString("") { "%02x".format(it) } == saved.second
    }

    suspend fun delete(id: String) = withContext(Dispatchers.IO) {
        requireRegion(id)
        target(id).delete()
        localMeta(id).delete()
        part(id).delete()
        partMarker(id).delete()
    }
}
