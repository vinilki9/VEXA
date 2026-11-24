package ru.vexa.offline

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext
import android.os.SystemClock
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts

/** Shared UI for both VEXA Client and VEXA Driver. Raster or vector MBTiles; routing data remains a separate optional index. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OfflineMapsScreen(mapBaseUrl: String, allowDebugHttp: Boolean, onBack: () -> Unit) {
    val context = LocalContext.current
    val repo = remember(mapBaseUrl, allowDebugHttp) {
        OfflineMapsRepository(context, mapBaseUrl, allowDebugHttp)
    }
    val scope = rememberCoroutineScope()
    val offlineSource = remember(context) { OfflineMbtilesServer(context) }
    val navigation = remember(context) { OfflineNavigation(context) }
    val importer = remember(context) { OfflineMapFileImporter(context) }
    var importRegionId by remember { mutableStateOf("central") }
    var importedBytes by remember { mutableLongStateOf(0L) }
    var addressRegions by remember { mutableStateOf<Set<String>>(emptySet()) }
    var routeRegions by remember { mutableStateOf<Set<String>>(emptySet()) }
    var renderableRegions by remember { mutableStateOf<Set<String>>(emptySet()) }
    var rows by remember { mutableStateOf<List<OfflineRegion>>(emptyList()) }
    var status by remember { mutableStateOf("Чтение установленных карт...") }
    var isBusy by remember { mutableStateOf(false) }
    var activeRegion by remember { mutableStateOf<String?>(null) }
    var activeJob by remember { mutableStateOf<Job?>(null) }
    var progressBytes by remember { mutableLongStateOf(0L) }
    var progressTotal by remember { mutableLongStateOf(0L) }
    var progressPhase by remember { mutableStateOf("Загрузка") }
    var toDelete by remember { mutableStateOf<String?>(null) }

    suspend fun reload() {
        rows = repo.localCatalog()
        navigation.status().let { addressRegions = it.addressRegions; routeRegions = it.routingRegions }
        renderableRegions = withContext(Dispatchers.IO) {
            offlineSource.refresh()
            offlineSource.renderableRegionIds()
        }
        try {
            rows = repo.refreshCatalog()
            status = if (rows.any { it.available }) "Каталог обновлён" else "Сервер пока не опубликовал карты округов"
        } catch (error: Exception) {
            status = "Нет связи с каталогом: ${error.message ?: "ошибка"}. Установленные пакеты доступны."
        }
    }
    val filePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null && !isBusy && activeRegion == null) {
            val region = importRegionId
            activeJob = scope.launch {
                isBusy = true
                status = "Импорт файла MBTiles..."
                importedBytes = 0L
                try {
                    val result = importer.install(region, uri) { bytes -> importedBytes = bytes }
                    OfflineMapMode.selectRegion(context, region)
                    status = "Карта установлена: ${result.format.uppercase()}, ${OfflineMapRules.formatBytes(result.sizeBytes)}. " +
                        "Откройте навигатор — выбран офлайн-режим."
                } catch (error: Exception) {
                    status = "Ошибка импорта: ${error.message}"
                } finally {
                    isBusy = false
                    activeJob = null
                    val resultMessage = status
                    reload()
                    status = resultMessage
                }
            }
        }
    }
    LaunchedEffect(repo) { reload() }
    DisposableEffect(repo) {
        onDispose { activeJob?.cancel() } // .part remains for resume on next visit
    }

    Scaffold(topBar = {
        TopAppBar(title = { Text("Офлайн-карты VEXA") }, navigationIcon = {
            IconButton(onClick = { activeJob?.cancel(); onBack() }) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Назад к настройкам")
            }
        })
    }) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Выберите федеральные округа. Карты хранятся на этом телефоне.",
                style = MaterialTheme.typography.bodyMedium)
            Text("Растровые PNG/JPEG/WebP и подготовленные векторные PBF работают без интернета. " +
                "Названия улиц в PBF доступны только с локальными глифами. " +
                "Офлайн-адреса и маршруты требуют навигационного индекса VEXA v1; " +
                "пока маршруты ограничены 90 км и не учитывают повороты и пробки.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text("Установка карты с телефона: выберите подготовленный файл central.mbtiles. " +
                "Файл OSM .pbf напрямую не подходит: он должен быть преобразован в MBTiles.",
                style = MaterialTheme.typography.bodySmall)
            Button(enabled = !isBusy && activeRegion == null, onClick = {
                importRegionId = "central"
                filePicker.launch(arrayOf("application/octet-stream", "application/vnd.sqlite3", "*/*"))
            }) { Text("Установить MBTiles ЦФО из файла") }
            if (isBusy && importedBytes > 0) Text("Скопировано: ${OfflineMapRules.formatBytes(importedBytes)}",
                style = MaterialTheme.typography.bodySmall)
            Text(status, style = MaterialTheme.typography.bodySmall)
            OutlinedButton(onClick = {
                if (!isBusy) scope.launch { isBusy = true; try { reload() } finally { isBusy = false } }
            }, enabled = !isBusy && activeRegion == null) { Text("Обновить каталог") }
            LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp),
                contentPadding = PaddingValues(bottom = 30.dp)) {
                items(rows, key = { it.id }) { region ->
                    Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surface)) {
                        Column(modifier = Modifier.fillMaxWidth().padding(14.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(region.title, style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold)
                            if (region.installed) Text(
                                "Адреса: ${if (region.id in addressRegions) "есть" else "нет"} · " +
                                "Дороги: ${if (region.id in routeRegions) "есть" else "нет"}",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                style = MaterialTheme.typography.bodySmall)
                            Text(when {
                                region.updateAvailable -> "Обновление ${region.version ?: ""} · ${OfflineMapRules.formatBytes(region.bytes)}"
                                region.installed -> "Скачана версия ${region.installedVersion}" +
                                    if (region.available) " · актуальность проверена по каталогу" else " · нет соединения с каталогом"
                                region.available -> "Доступна версия ${region.version} · ${OfflineMapRules.formatBytes(region.bytes)}"
                                else -> "Регион пока не опубликован на сервере"
                            }, style = MaterialTheme.typography.bodySmall)
                            if (region.partialBytes > 0 && !region.installed) {
                                Text("Есть частичная загрузка: ${OfflineMapRules.formatBytes(region.partialBytes)}",
                                    style = MaterialTheme.typography.bodySmall)
                            }
                            if (activeRegion == region.id && progressTotal > 0) {
                                LinearProgressIndicator(progress = { (progressBytes.toFloat() / progressTotal.toFloat()).coerceIn(0f,1f) },
                                    modifier = Modifier.fillMaxWidth())
                                Text("$progressPhase · ${OfflineMapRules.formatBytes(progressBytes)} / ${OfflineMapRules.formatBytes(progressTotal)}",
                                    style = MaterialTheme.typography.bodySmall)
                            }
                            Row(modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                                horizontalArrangement = Arrangement.spacedBy(7.dp),
                                verticalAlignment = Alignment.CenterVertically) {
                                if (activeRegion == region.id) {
                                    OutlinedButton(onClick = { activeJob?.cancel() }) { Text("Пауза") }
                                } else if (region.downloadable && (!region.installed || region.updateAvailable)) {
                                    Button(enabled = activeRegion == null, onClick = {
                                        status = "Загрузка округа: ${region.title}"
                                        activeRegion = region.id
                                        progressBytes = region.partialBytes
                                        progressTotal = region.bytes
                                        progressPhase = "Загрузка"
                                        activeJob = scope.launch {
                                            var lastProgressMs = 0L
                                            try {
                                                repo.download(region.id) { sent, total, phase ->
                                                    val now = SystemClock.elapsedRealtime()
                                                    if (now - lastProgressMs >= 250L || phase != progressPhase || sent == total) {
                                                        lastProgressMs = now
                                                        withContext(Dispatchers.Main) {
                                                            progressBytes = sent
                                                            progressTotal = total
                                                            progressPhase = phase
                                                        }
                                                    }
                                                }
                                                status = "Пакет ${region.title} загружен и проверен"
                                            } catch (cancel: kotlinx.coroutines.CancellationException) {
                                                status = "Загрузка приостановлена — можно продолжить позже"
                                                throw cancel
                                            } catch (error: Exception) {
                                                status = "Ошибка загрузки ${region.title}: ${error.message}"
                                            } finally {
                                                activeRegion = null
                                                activeJob = null
                                                withContext(NonCancellable) {
                                                    val installed = repo.localCatalog().associateBy { it.id }
                                                    // Preserve the last remote catalog when a transfer is paused offline.
                                                    renderableRegions = withContext(Dispatchers.IO) {
                                                        offlineSource.refresh()
                                                        offlineSource.renderableRegionIds()
                                                    }
                                                    rows = rows.map { current ->
                                                        val disk = installed[current.id]
                                                        current.copy(
                                                            installedVersion = disk?.installedVersion,
                                                            installedSha = disk?.installedSha,
                                                            partialBytes = disk?.partialBytes ?: 0L
                                                        )
                                                    }
                                                }
                                            }
                                        }
                                    }) { Text(when {
                                        region.updateAvailable -> "Обновить"
                                        region.partialBytes > 0 -> "Продолжить"
                                        else -> "Скачать"
                                    }) }
                                }
                                if (region.installed) {
                                    if (region.id in renderableRegions) {
                                        Button(enabled = activeRegion == null && !isBusy, onClick = {
                                            OfflineMapMode.selectRegion(context, region.id)
                                            status = "Выбран округ ${region.title}. Вернитесь на главную карту."
                                        }) { Text("Показать на карте") }
                                    }
                                    OutlinedButton(enabled = activeRegion == null && !isBusy, onClick = {
                                        scope.launch {
                                            isBusy = true
                                            try {
                                                status = if (repo.verifyInstalled(region.id))
                                                    "SHA-256 ${region.title}: совпадает" else "SHA-256 ${region.title}: пакет повреждён"
                                            } catch (error: Exception) { status = "Ошибка проверки: ${error.message}" }
                                            finally { isBusy = false }
                                        }
                                    }) { Text("Проверить") }
                                }
                                if (region.installed || region.partialBytes > 0) {
                                    TextButton(enabled = activeRegion == null && !isBusy,
                                        onClick = { toDelete = region.id }) { Text("Удалить") }
                                }
                            }
                            if (region.installed && region.id !in renderableRegions) {
                                Text("Этот пакет несовместим с локальным отображением. Для PBF нужна metadata.json.vector_layers и хотя бы слой дорог.",
                                    style = MaterialTheme.typography.bodySmall)
                            }
                            if (region.available && !region.downloadable && !region.installed) {
                                Text("Скачивание отключено администратором сервера",
                                    style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }
        }
    }
    toDelete?.let { id ->
        AlertDialog(onDismissRequest = { toDelete = null },
            title = { Text("Удалить пакет карты?") },
            text = { Text("Файлы выбранного округа будут удалены только с этого телефона.") },
            confirmButton = { TextButton(onClick = {
                toDelete = null
                scope.launch {
                    isBusy = true
                    try { repo.delete(id); reload() }
                    finally { isBusy = false }
                }
            }) { Text("Удалить") } },
            dismissButton = { TextButton(onClick = { toDelete = null }) { Text("Отмена") } })
    }
}
