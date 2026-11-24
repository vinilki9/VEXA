pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "VEXA-client"
include(":app", ":vexa-map-offline")
project(":vexa-map-offline").projectDir = file("../shared/vexa-map-offline")
