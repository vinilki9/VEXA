package ru.vexa.offline

/** MBTiles stores tiles in TMS order; MapLibre requests XYZ coordinates. */
object OfflineTileMath {
    fun tmsRow(zoom: Int, x: Long, y: Long): Long? {
        if (zoom !in 0..22) return null
        val extent = 1L shl zoom
        if (x !in 0 until extent || y !in 0 until extent) return null
        return extent - 1L - y
    }
    fun safeTilePath(path: String): Triple<Int, Long, Long>? {
        val groups = Regex("^/tiles/([0-9]{1,2})/([0-9]{1,10})/([0-9]{1,10})$").matchEntire(path)
            ?.groupValues ?: return null
        val z = groups[1].toIntOrNull() ?: return null
        val x = groups[2].toLongOrNull() ?: return null
        val y = groups[3].toLongOrNull() ?: return null
        if (tmsRow(z, x, y) == null) return null
        return Triple(z, x, y)
    }
}
