package ai.argus.nativeauth

import android.content.Context
import android.content.Intent
import io.github.jan.supabase.SupabaseClient
import io.github.jan.supabase.auth.Auth
import io.github.jan.supabase.auth.FlowType
import io.github.jan.supabase.auth.SessionManager
import io.github.jan.supabase.auth.SignOutScope
import io.github.jan.supabase.auth.auth
import io.github.jan.supabase.auth.handleDeeplinks
import io.github.jan.supabase.auth.user.UserSession
import io.github.jan.supabase.createSupabaseClient
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

sealed class ArgusAuthException(message: String) : Exception(message) {
    class SignedOut : ArgusAuthException("signed out")
    class Rejected(val status: Int, val code: String?) : ArgusAuthException("rejected $status $code")
}

data class SignInOutcome(val userId: String, val claimedConversationId: String?)

/** Supabase session persistence in the Keystore-backed store instead of plain preferences. */
private class SecureSessionManager(private val store: SecureStore) : SessionManager {
    private val json = Json { ignoreUnknownKeys = true }
    override suspend fun saveSession(session: UserSession) = store.put("session", json.encodeToString(session))
    override suspend fun loadSession(): UserSession? = store.get("session")?.let { json.decodeFromString(it) }
    override suspend fun deleteSession() = store.remove("session")
}

/**
 * Argus owns entry (captcha, limits, allowlist, guest claim). supabase-kt owns
 * the session afterwards: storage, refresh, revoke, recovery callbacks.
 */
class ArgusNativeClient(
    context: Context,
    supabaseUrl: String,
    anonKey: String,
    argusBase: String,
    storeName: String,
    handoffTransport: HandoffTransport = HandoffTransport.SCOPED_COOKIES,
    deviceIp: String? = null,
) {
    val secureStore = SecureStore(context, storeName)
    val transport = BearerTransport(argusBase, deviceIp)
    val handoffs = HandoffStore(secureStore, handoffTransport)
    val boundary = AccountBoundary()
    private val json = Json { ignoreUnknownKeys = true }
    // Single-flight refresh owned by the app, whatever the SDK guarantees.
    private val refreshMutex = Mutex()

    val supabase: SupabaseClient = createSupabaseClient(supabaseUrl, anonKey) {
        install(Auth) {
            flowType = FlowType.PKCE
            scheme = "argusnativeproof"
            host = "auth-callback"
            sessionManager = SecureSessionManager(secureStore)
            alwaysAutoRefresh = false
        }
    }

    suspend fun startGuest(captchaToken: String): String {
        val bearer = supabase.auth.currentAccessTokenOrNull()
        val response = authCall("/auth/guest", bearer, buildJsonObject {
            put("captcha_token", captchaToken)
            put("language", "en")
        })
        if (response.status != 200) throw rejection(response)
        if (response.body["reused"]?.jsonPrimitive?.content != "true") adopt(response)
        return response.body["user"]?.jsonObject?.get("id")?.jsonPrimitive?.content.orEmpty()
    }

    suspend fun signIn(email: String, password: String, captchaToken: String): SignInOutcome {
        val response = authCall("/auth/login", null, buildJsonObject {
            put("email", email)
            put("password", password)
            put("captcha_token", captchaToken)
        })
        if (response.status != 200) {
            if (response.body["session"] != null) {
                adopt(response)
                supabase.auth.signOut(SignOutScope.LOCAL)
            }
            throw rejection(response)
        }
        adopt(response)
        val claim = response.body["guest_claim"] as? JsonObject
        return SignInOutcome(
            userId = response.body["user"]?.jsonObject?.get("id")?.jsonPrimitive?.content.orEmpty(),
            claimedConversationId = claim?.get("conversation_id")?.jsonPrimitive?.content,
        )
    }

    suspend fun createHandoff(destinationEmail: String, conversationId: String, kind: String = "existing_account") {
        val response = authCall("/auth/guest/handoffs", accessToken(), buildJsonObject {
            put("handoff_kind", kind)
            put("destination_email", destinationEmail)
            put("source_conversation_id", conversationId)
        })
        if (response.status != 201) throw rejection(response)
    }

    suspend fun request(method: String, path: String, body: JsonElement? = null, cacheKey: String? = null): ApiResponse {
        val started = boundary.begin()
        var response = transport.send(method, path, accessToken(), body)
        if (response.status == 401) {
            runCatching { refreshMutex.withLock { supabase.auth.refreshCurrentSession() } }.onFailure {
                boundary.end()
                throw ArgusAuthException.SignedOut()
            }
            response = transport.send(method, path, accessToken(), body)
            if (response.status == 401) {
                signOut()
                throw ArgusAuthException.SignedOut()
            }
        }
        return boundary.deliver(response, started, cacheKey)
    }

    /** Revokes this device's session at Supabase and clears local state. */
    suspend fun signOut() {
        boundary.end()
        handoffs.clear()
        supabase.auth.signOut(SignOutScope.LOCAL)
    }

    suspend fun requestRecovery(email: String, captchaToken: String? = null) {
        supabase.auth.resetPasswordForEmail(email, redirectUrl = "argusnativeproof://auth-callback", captchaToken = captchaToken)
    }

    /** For an Activity receiving the callback intent. */
    fun handleCallback(intent: Intent) = supabase.handleDeeplinks(intent)

    /** For tests: exchange the code from a callback URL on this install. */
    suspend fun completeCallback(code: String) {
        supabase.auth.exchangeCodeForSession(code)
        boundary.end()
    }

    private suspend fun accessToken(): String {
        fun expiring() = supabase.auth.currentSessionOrNull()
            ?.let { it.expiresAt.epochSeconds - 30 <= System.currentTimeMillis() / 1000 }
            ?: throw ArgusAuthException.SignedOut()
        if (expiring()) {
            runCatching { refreshMutex.withLock { if (expiring()) supabase.auth.refreshCurrentSession() } }
                .onFailure {
                    boundary.end()
                    throw ArgusAuthException.SignedOut()
                }
        }
        return supabase.auth.currentAccessTokenOrNull() ?: throw ArgusAuthException.SignedOut()
    }

    private fun authCall(path: String, bearer: String?, body: JsonElement): ApiResponse {
        val response = transport.send("POST", path, bearer, body, handoffs.headers(path))
        handoffs.absorb(response)
        return response
    }

    private suspend fun adopt(response: ApiResponse) {
        val session = response.body["session"] ?: return
        if (session is JsonNull) return
        boundary.end()
        supabase.auth.importSession(json.decodeFromJsonElement(UserSession.serializer(), session))
    }

    private fun rejection(response: ApiResponse) = ArgusAuthException.Rejected(response.status, response.problemCode)
}
