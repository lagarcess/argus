plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}
fun localAuthSetting(name: String): String = providers.environmentVariable(name).orElse("").get()
fun quoted(value: String): String = "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r") + "\""

android {
    namespace = "ai.argus.foundation"
    compileSdk = 36
    defaultConfig {
        applicationId = "ai.argus.foundation.sample"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1-sample"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("boolean", "LOCAL_AUTH_ENABLED", "false")
        listOf("API_URL", "SUPABASE_URL", "SUPABASE_ANON_KEY", "CAPTCHA_TOKEN", "RECOVERY_URL").forEach {
            buildConfigField("String", "AUTH_$it", quoted(""))
        }
    }
    buildTypes {
        getByName("debug") {
            buildConfigField("boolean", "LOCAL_AUTH_ENABLED", (localAuthSetting("ARGUS_ANDROID_LOCAL_AUTH") == "true").toString())
            listOf("API_URL", "SUPABASE_URL", "SUPABASE_ANON_KEY", "CAPTCHA_TOKEN", "RECOVERY_URL").forEach {
                buildConfigField("String", "AUTH_$it", quoted(localAuthSetting("ARGUS_ANDROID_$it")))
            }
        }
    }
    buildFeatures { compose = true; buildConfig = true }
    // Verified profile language can differ from the device language, including offline.
    bundle { language { enableSplit = false } }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    lint {
        warningsAsErrors = true
        // A deliberately pinned API/toolchain is not a rolling latest-version policy.
        disable += setOf("OldTargetApi", "AndroidGradlePluginVersion", "GradleDependency")
    }
}
dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.08.01")
    implementation(composeBom)
    androidTestImplementation(composeBom)
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation(platform("io.github.jan-tennert.supabase:bom:3.2.6"))
    implementation("io.github.jan-tennert.supabase:auth-kt")
    implementation("io.ktor:ktor-client-okhttp:3.3.1")
    implementation("com.squareup.okhttp3:okhttp:5.1.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
    testImplementation("com.squareup.okhttp3:mockwebserver:5.1.0")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    androidTestImplementation("androidx.test.uiautomator:uiautomator:2.3.0")
}
