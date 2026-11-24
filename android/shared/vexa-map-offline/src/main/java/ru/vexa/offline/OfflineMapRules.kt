package ru.vexa.offline

/** A single district registry shared by passenger and driver applications. */
object OfflineMapRules {
    val districts: LinkedHashMap<String, String> = linkedMapOf(
        "central" to "Центральный",
        "northwestern" to "Северо-Западный",
        "southern" to "Южный",
        "north-caucasus" to "Северо-Кавказский",
        "volga" to "Приволжский",
        "ural" to "Уральский",
        "siberian" to "Сибирский",
        "far-eastern" to "Дальневосточный"
    )
    fun validRegion(id: String) = districts.containsKey(id)
    fun validDigest(sha: String) = sha.length == 64 && sha.all { it in '0'..'9' || it in 'a'..'f' }
    fun canResume(offset: Long, total: Long, expectedDigest: String, savedDigest: String): Boolean =
        offset > 0 && offset < total && validDigest(expectedDigest) && expectedDigest == savedDigest
    fun formatBytes(bytes: Long): String = when {
        bytes < 1024L * 1024L -> "${bytes / 1024L} КБ"
        bytes < 1024L * 1024L * 1024L -> "%.1f МБ".format(java.util.Locale.ROOT, bytes / 1048576.0)
        else -> "%.2f ГБ".format(java.util.Locale.ROOT, bytes / 1073741824.0)
    }
}
