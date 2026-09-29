package ai.argus.foundation.auth

import ai.argus.foundation.BuildConfig
import java.net.URI

/** Only disposable, local development services are accepted by this opt-in build. */
data class AuthEnvironment(
    val apiBaseUrl: String,
    val supabaseUrl: String,
    val supabaseAnonKey: String,
    val captchaToken: String,
    val recoveryUrl: String,
) {
    companion object {
        fun fromBuildConfig(): AuthEnvironment? {
            if (!BuildConfig.DEBUG || !BuildConfig.LOCAL_AUTH_ENABLED) return null
            return validated(
                BuildConfig.AUTH_API_URL,
                BuildConfig.AUTH_SUPABASE_URL,
                BuildConfig.AUTH_SUPABASE_ANON_KEY,
                BuildConfig.AUTH_CAPTCHA_TOKEN,
                BuildConfig.AUTH_RECOVERY_URL,
            )
        }

        internal fun validated(
            apiBaseUrl: String,
            supabaseUrl: String,
            supabaseAnonKey: String,
            captchaToken: String,
            recoveryUrl: String,
        ): AuthEnvironment? {
            if (supabaseAnonKey.isBlank() || captchaToken.isBlank()) return null
            if (!listOf(apiBaseUrl, supabaseUrl, recoveryUrl).all(::isLocalUrl)) return null
            if (URI(recoveryUrl).path != "/auth/forgot-password") return null
            return AuthEnvironment(apiBaseUrl.trimEnd('/'), supabaseUrl.trimEnd('/'), supabaseAnonKey, captchaToken, recoveryUrl)
        }

        private fun isLocalUrl(value: String): Boolean = runCatching {
            val uri = URI(value)
            uri.scheme in setOf("http", "https") &&
                uri.host in setOf("localhost", "127.0.0.1", "10.0.2.2") &&
                uri.port in 1..65535 && uri.userInfo == null && uri.query == null && uri.fragment == null
        }.getOrDefault(false)
    }
}
