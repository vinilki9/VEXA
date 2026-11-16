
package ru.vexa.driver

import android.app.Application
import ru.dgis.sdk.DGis
import ru.dgis.sdk.Context

class VexaApplication : Application() {

    lateinit var sdkContext: Context
        private set

    override fun onCreate() {
        super.onCreate()
        sdkContext = DGis.initialize(this)
    }
}
