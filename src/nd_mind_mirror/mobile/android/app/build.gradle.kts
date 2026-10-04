plugins {
    id("com.android.application")
}

android {
    namespace = "com.ndmindmirror.android"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.ndmindmirror.android"
        minSdk = 26
        targetSdk = 37
        versionCode = 11
        versionName = "0.6.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlin {
        jvmToolchain(17)
    }
}
