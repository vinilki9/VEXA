
package ru.vexa.driver

import android.app.Application

class VexaApplication : Application() {
    override fun onCreate() {
        super.onCreate()

        // Восстанавливаем защищённую сессию водителя.
        DriverApiClient.initialize(this)

    }
}
