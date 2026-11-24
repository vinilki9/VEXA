package ru.vexa.offline

/** These rules are deliberately independent of UI/MapLibre so they can be tested on the JVM. */
enum class DriverMapPerspective(val label: String) {
    TWO_D("2D"), THREE_D("3D");
    fun next(): DriverMapPerspective = if (this == TWO_D) THREE_D else TWO_D
}

object NavigationCameraRules {
    const val PASSENGER_TILT = 0.0
    const val PASSENGER_BEARING = 0.0
    fun driverTilt(mode: DriverMapPerspective): Double = if (mode == DriverMapPerspective.THREE_D) 55.0 else 0.0
    fun driverBearing(mode: DriverMapPerspective, gpsHeading: Double?): Double {
        if (mode == DriverMapPerspective.TWO_D || gpsHeading == null || !gpsHeading.isFinite()) return 0.0
        return ((gpsHeading % 360.0) + 360.0) % 360.0
    }
}
