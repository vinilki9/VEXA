plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "ru.vexa.client"
    compileSdk = 35

    defaultConfig {
        applicationId = "ru.vexa.client"
        minSdk = 26
        targetSdk = 35
        versionCode = 19
        versionName = "0.3.19"
        val host = providers.gradleProperty("vexaServerHost").orElse("45.143.139.162").get()
        val scheme = providers.gradleProperty("vexaServerScheme").orElse("https").get()
        val cityCode = providers.gradleProperty("vexaCityCode").orElse("obolensk").get()
        require(cityCode.matches(Regex("[a-z0-9_-]{1,80}"))) { "Invalid vexaCityCode" }
        buildConfigField("String", "VEXA_CITY_CODE", "\"${cityCode}\"")
        require(host.matches(Regex("[A-Za-z0-9.:-]+"))) { "Invalid vexaServerHost" }
        require(scheme in listOf("http", "https")) { "Invalid vexaServerScheme" }
        buildConfigField("String", "VEXA_API_BASE_URL", "\"${scheme}://${host}\"")
        buildConfigField("String", "VEXA_MAP_BASE_URL", "\"${scheme}://${host}/maps\"")

    }

    buildTypes {
        getByName("debug") { manifestPlaceholders["vexaCleartext"] = "true" }
        getByName("release") {
            manifestPlaceholders["vexaCleartext"] = "false"
            // Real-server addresses are supplied at build time; no local/LAN HTTP in a release.
            val apiUrl = providers.gradleProperty("vexaReleaseApiBaseUrl")
                .orElse("https://45.143.139.162").get().trimEnd('/')
            val mapUrl = providers.gradleProperty("vexaReleaseMapBaseUrl")
                .orElse("https://45.143.139.162/maps").get().trimEnd('/')
            val buildingRelease = gradle.startParameter.taskNames.any {
                it.contains("release", ignoreCase = true) || it.contains("publish", ignoreCase = true)
            }
            if (buildingRelease) {
                require(apiUrl.startsWith("https://") && !apiUrl.contains(".invalid")) {
                    "Set -PvexaReleaseApiBaseUrl=https://your-domain before release builds"
                }
                require(mapUrl.startsWith("https://") && !mapUrl.contains(".invalid")) {
                    "Set -PvexaReleaseMapBaseUrl=https://your-domain/maps before release builds"
                }
                require(!apiUrl.contains('"') && !mapUrl.contains('"')) {
                    "VEXA release URLs must not contain quotes"
                }
            }
            buildConfigField("String", "VEXA_API_BASE_URL", "\"${apiUrl}\"")
            buildConfigField("String", "VEXA_MAP_BASE_URL", "\"${mapUrl}\"")
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation(project(":vexa-map-offline"))
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    // Open-source rendering for VEXA MAP
    implementation("org.maplibre.gl:android-sdk:11.8.0")


    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.activity:activity-compose:1.10.0")

    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    debugImplementation("androidx.compose.ui:ui-tooling")
}
