package ru.vexa.client

import android.app.Application
import org.maplibre.android.MapLibre

class VexaApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        MapLibre.getInstance(this)
        ApiClient.initializeSession(this)
    }
}
