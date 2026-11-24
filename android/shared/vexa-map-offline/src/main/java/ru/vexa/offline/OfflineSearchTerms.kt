package ru.vexa.offline

import java.util.Locale

/** Normalisation shared by search queries and the index builder (Unicode case, ё/е). */
object OfflineSearchTerms {
    fun tokens(query: String): List<String> = query.lowercase(Locale.ROOT).replace('ё', 'е')
        .split(Regex("[^\\p{L}\\p{N}]+"))
        .filter { it.isNotBlank() }.take(8)
}
