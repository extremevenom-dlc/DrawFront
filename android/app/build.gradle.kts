import java.util.Base64

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

// The signing key is stored as text (drawfont-sideload.p12.b64) and turned back into a keystore file here.
val sideloadKeystore = layout.buildDirectory.file("sideload.p12").get().asFile
sideloadKeystore.parentFile.mkdirs()
sideloadKeystore.writeBytes(Base64.getMimeDecoder().decode(rootProject.file("drawfont-sideload.p12.b64").readText()))

// CI passes -PappVersion=1.2.3 (from the release tag) and -PappVersionCode=<run number>.
val appVersion = (project.findProperty("appVersion") as String?) ?: "0.0.0"
val appVersionCode = ((project.findProperty("appVersionCode") as String?) ?: "1").toInt()

android {
    namespace = "com.drawfont.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.drawfont.app"
        minSdk = 24
        targetSdk = 34
        versionCode = appVersionCode
        versionName = appVersion
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64") }
    }

    // Every release MUST be signed with the same key, otherwise Android refuses to update the app.
    // This key is public on purpose (hobby/side-loaded app); see README "Android signing".
    signingConfigs {
        create("sideload") {
            storeFile = sideloadKeystore
            storeType = "pkcs12"
            storePassword = "drawfont-sideload"
            keyAlias = "drawfont"
            keyPassword = "drawfont-sideload"
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("sideload")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

chaquopy {
    defaultConfig {
        version = "3.11"
        pip { install("fonttools") }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
}

// The font engine is the SAME fontcore.py the Windows app uses - copied in before every build.
val syncCore by tasks.registering(Copy::class) {
    from(rootProject.file("../fontcore.py"))
    into(layout.projectDirectory.dir("src/main/python"))
}
tasks.named("preBuild") { dependsOn(syncCore) }
// Gradle 8 insists this is explicit: Chaquopy's "merge Python sources" step reads the folder syncCore writes into.
tasks.matching { it.name.startsWith("merge") && it.name.endsWith("PythonSources") }.configureEach {
    dependsOn(syncCore)
}
