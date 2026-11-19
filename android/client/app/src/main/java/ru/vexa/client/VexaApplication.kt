
package ru.vexa.client

import android.app.Application
import ru.dgis.sdk.DGis
import ru.dgis.sdk.Context

class VexaApplication : Application() {

    companion object {
        lateinit var instance: VexaApplication
            private set
    }

    lateinit var sdkContext: Context
        private set

    override fun onCreate() {
        super.onCreate()

        instance = this
        sdkContext = DGis.initialize(this)
    }
}
