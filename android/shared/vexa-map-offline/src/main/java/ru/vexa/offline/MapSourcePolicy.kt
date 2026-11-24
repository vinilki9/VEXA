package ru.vexa.offline

/** Shared display source policy for Client, Driver and standalone Navigator.
 * A map source does not guarantee that tiles or routing data exist on its server.
 */
enum class EffectiveMapSource { OFFLINE, ONLINE, UNAVAILABLE }

object MapSourcePolicy {
    fun choose(mode: OfflineMapMode, hasOfflinePackage: Boolean, hasInternet: Boolean): EffectiveMapSource = when (mode) {
        OfflineMapMode.AUTO -> when {
            hasOfflinePackage -> EffectiveMapSource.OFFLINE
            hasInternet -> EffectiveMapSource.ONLINE
            else -> EffectiveMapSource.UNAVAILABLE
        }
        OfflineMapMode.ONLINE -> when {
            hasInternet -> EffectiveMapSource.ONLINE
            hasOfflinePackage -> EffectiveMapSource.OFFLINE
            else -> EffectiveMapSource.UNAVAILABLE
        }
        OfflineMapMode.OFFLINE -> when {
            hasOfflinePackage -> EffectiveMapSource.OFFLINE
            hasInternet -> EffectiveMapSource.ONLINE // Explicit feedback is shown by the UI
            else -> EffectiveMapSource.UNAVAILABLE
        }
    }
}
