
package ru.vexa.client

import android.content.Context
import android.os.Handler
import android.os.Looper
import ru.dgis.sdk.directory.SearchManager
import ru.dgis.sdk.directory.SuggestQueryBuilder

data class AddressResult(
    val name: String,
    val latitude: Double,
    val longitude: Double
)

object AddressSearch {

    private val mainHandler = Handler(Looper.getMainLooper())
    private val managerLock = Any()

    @Volatile
    private var searchManager: SearchManager? = null

    private fun getSearchManager(context: Context): SearchManager {
        searchManager?.let {
            return it
        }

        synchronized(managerLock) {
            searchManager?.let {
                return it
            }

            val sdkContext =
                (context.applicationContext as VexaApplication).sdkContext

            return SearchManager.createSmartManager(sdkContext).also {
                searchManager = it
            }
        }
    }

    fun search(
        context: Context,
        query: String,
        onResult: (List<AddressResult>) -> Unit,
        onError: (String) -> Unit
    ) {
        val normalizedQuery = query.trim()

        if (normalizedQuery.isEmpty()) {
            mainHandler.post {
                onResult(emptyList())
            }
            return
        }

        try {
            val manager = getSearchManager(context)

            val request = SuggestQueryBuilder(normalizedQuery)
                .setLimit(10)
                .build()

            manager.suggest(request)
                .onResult { suggestResult ->

                    val addresses = suggestResult.suggests
                        .orEmpty()
                        .mapNotNull { suggestion ->

                            var addressResult: AddressResult? = null

                            suggestion.handler.match(
                                objectHandler = { objectHandler ->

                                    val item = objectHandler.item
                                    val point = item.markerPosition?.point

                                    if (point != null) {
                                        val name = suggestion.title

                                        if (name.isNotBlank()) {
                                            addressResult = AddressResult(
                                                name = name,
                                                latitude = point.latitude.value,
                                                longitude = point.longitude.value
                                            )
                                        }
                                    }
                                },
                                performSearchHandler = {
                                    // Поисковый запрос без готовых координат.
                                },
                                incompleteTextHandler = {
                                    // Незавершённый текст не является адресом.
                                }
                            )

                            addressResult
                        }
                        .distinctBy {
                            "${it.latitude}:${it.longitude}"
                        }

                    mainHandler.post {
                        onResult(addresses)
                    }
                }
                .onError { error ->

                    val message = error.message
                        ?: "Не удалось выполнить поиск адреса."

                    mainHandler.post {
                        onError(message)
                    }
                }

        } catch (error: Exception) {

            val message = error.message
                ?: "Ошибка запуска поиска адреса."

            mainHandler.post {
                onError(message)
            }
        }
    }
}
