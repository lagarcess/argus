@file:OptIn(io.github.jan.supabase.annotations.SupabaseInternal::class, kotlin.time.ExperimentalTime::class)

package ai.argus.foundation.auth

import android.content.Context
import io.github.jan.supabase.SupabaseClient
import io.github.jan.supabase.auth.Auth
import io.github.jan.supabase.auth.MemoryCodeVerifierCache
import io.github.jan.supabase.auth.MemorySessionManager
import io.github.jan.supabase.auth.SignOutScope
import io.github.jan.supabase.auth.auth
import io.github.jan.supabase.auth.user.UserSession
import io.github.jan.supabase.createSupabaseClient
import io.github.jan.supabase.exceptions.RestException
import io.github.jan.supabase.logging.LogLevel
import io.ktor.client.engine.okhttp.OkHttp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlin.time.Duration.Companion.seconds

internal class SupabaseSessionSdk(private val client: SupabaseClient) : SessionSdk {
    override suspend fun importSession(session: UserSession) = sanitized {
        client.auth.importSession(session, autoRefresh = false)
    }

    override suspend fun refresh(session: UserSession): UserSession = sanitized(refresh = true) {
        client.auth.refreshSession(session.refreshToken)
    }

    override suspend fun revoke(session: UserSession) = sanitized {
        // SDK 3.2.6 AdminApiImpl.signOut uses the ordinary logout route with THIS bearer.
        // AuthImpl.signOut swallows 401/403/404 before clearing storage; this method does not.
        // Source: supabase-community/supabase-kt, 3.2.6, auth/.../admin/AdminApi.kt.
        client.auth.admin.signOut(session.accessToken, SignOutScope.LOCAL)
    }

    override suspend fun clear() = sanitized { client.auth.clearSession() }

    private suspend fun <T> sanitized(refresh: Boolean = false, block: suspend () -> T): T = try {
        block()
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (failure: RestException) {
        throw SessionFailure(when {
            refresh && failure.statusCode in setOf(400, 401, 403) -> SessionProblem.REJECTED_SESSION
            failure.statusCode == 429 || failure.statusCode >= 500 -> SessionProblem.VERIFICATION_UNAVAILABLE
            else -> SessionProblem.REVOCATION
        })
    } catch (_: Exception) {
        // SDK RestException includes request headers. Never forward its message or cause.
        throw SessionFailure(SessionProblem.NETWORK)
    }
}

internal fun createSessionSdk(config: AuthEnvironment): SupabaseSessionSdk {
    val client = createSupabaseClient(config.supabaseUrl, config.supabaseAnonKey) {
        defaultLogLevel = LogLevel.NONE
        useHTTPS = config.supabaseUrl.startsWith("https://")
        coroutineDispatcher = Dispatchers.IO
        requestTimeout = 20.seconds
        httpEngine = OkHttp.create { config { followRedirects(false); followSslRedirects(false) } }
        httpConfig { followRedirects = false }
        install(Auth) {
            autoLoadFromStorage = false
            autoSaveToStorage = false
            alwaysAutoRefresh = false
            enableLifecycleCallbacks = false
            sessionManager = MemorySessionManager()
            codeVerifierCache = MemoryCodeVerifierCache()
        }
    }
    return SupabaseSessionSdk(client)
}

fun createSessionController(context: Context, config: AuthEnvironment): SessionController = SessionController(
    ArgusSessionBackend(config.apiBaseUrl, config.captchaToken),
    EncryptedSessionVault(context.applicationContext),
    createSessionSdk(config),
)
