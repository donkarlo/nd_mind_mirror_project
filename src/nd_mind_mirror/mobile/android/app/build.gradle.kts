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
        versionCode = 8
        versionName = "0.3.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlin {
        jvmToolchain(17)
    }
}
