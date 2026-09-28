@file:OptIn(kotlin.time.ExperimentalTime::class)

package ai.argus.foundation.auth

import io.github.jan.supabase.auth.user.UserSession
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import kotlinx.serialization.json.put
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import kotlin.time.Instant

internal val sessionJson = Json { ignoreUnknownKeys = true }
// Python's provider DTO emits null for optional fields whose Kotlin SDK models use
// a non-null default (for example factors=[]). Required credentials have no default.
private val loginSessionJson = Json(sessionJson) { coerceInputValues = true }

internal class ArgusSessionBackend(
    private val baseUrl: String,
    private val captchaToken: String,
    private val client: OkHttpClient = OkHttpClient.Builder()
        .followRedirects(false).followSslRedirects(false)
        .callTimeout(20, TimeUnit.SECONDS).build(),
    private val dispatcher: CoroutineDispatcher = Dispatchers.IO,
) : SessionBackend {
    override suspend fun signIn(email: String, password: String): StoredSession {
        val body = buildJsonObject {
            put("email", email)
            put("password", password)
            put("captcha_token", captchaToken)
        }.toString().toRequestBody("application/json".toMediaType())
        val payload = request(Request.Builder().url("${baseUrl.trimEnd('/')}/api/v1/auth/login")
            .post(body).build(), login = true)
        return parseResponse {
            val raw = payload.getValue("session").jsonObject
            val expiry = raw["expires_at"]?.jsonPrimitive?.longOrNull
                ?: throw SessionFailure(SessionProblem.INVALID_RESPONSE)
            val session = loginSessionJson.decodeFromJsonElement(UserSession.serializer(), raw)
                .copy(expiresAt = Instant.fromEpochSeconds(expiry))
            val owner = session.user?.id?.takeIf(String::isNotBlank)
                ?: throw SessionFailure(SessionProblem.INVALID_RESPONSE)
            if (session.accessToken.isBlank() || session.refreshToken.isBlank() || session.expiresIn <= 0) {
                throw SessionFailure(SessionProblem.INVALID_RESPONSE)
            }
            val guest = raw["user"]?.jsonObject?.get("is_anonymous")?.jsonPrimitive?.booleanOrNull == true
            StoredSession(session, owner, if (guest) AccountKind.GUEST else AccountKind.UNKNOWN)
        }
    }

    override suspend fun me(accessToken: String): VerifiedAccount {
        val payload = request(Request.Builder().url("${baseUrl.trimEnd('/')}/api/v1/me")
            .header("Authorization", "Bearer $accessToken").get().build())
        return parseResponse {
            val kind = when (payload.string("account_kind")) {
                "registered" -> AccountKind.REGISTERED
                "guest" -> AccountKind.GUEST
                else -> throw SessionFailure(SessionProblem.INVALID_RESPONSE)
            }
            val user = payload.getValue("user").jsonObject
            val id = user.string("id")?.takeIf(String::isNotBlank)
                ?: throw SessionFailure(SessionProblem.INVALID_RESPONSE)
            VerifiedAccount(kind, SessionProfile(id, user.string("email"), user.string("display_name"),
                user.string("language"), user.string("locale")))
        }
    }

    private suspend fun request(request: Request, login: Boolean = false): JsonObject = withContext(dispatcher) {
        try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    throw SessionFailure(when {
                        response.code in setOf(401, 403) -> if (login) SessionProblem.INVALID_CREDENTIALS else SessionProblem.REJECTED_SESSION
                        response.code == 429 || response.code >= 500 -> SessionProblem.VERIFICATION_UNAVAILABLE
                        else -> SessionProblem.INVALID_RESPONSE
                    })
                }
                val body = response.body ?: throw SessionFailure(SessionProblem.INVALID_RESPONSE)
                val source = body.source()
                if (source.request(1_048_577)) throw SessionFailure(SessionProblem.INVALID_RESPONSE)
                parseResponse { sessionJson.parseToJsonElement(source.readUtf8()).jsonObject }
            }
        } catch (_: IOException) {
            throw SessionFailure(SessionProblem.NETWORK)
        }
    }
}

internal fun JsonObject.string(key: String): String? = get(key)?.takeUnless { it == JsonNull }?.jsonPrimitive?.contentOrNull

internal inline fun <T> parseResponse(block: () -> T): T = try {
    block()
} catch (failure: SessionFailure) {
    throw failure
} catch (_: IllegalArgumentException) {
    throw SessionFailure(SessionProblem.INVALID_RESPONSE)
} catch (_: NoSuchElementException) {
    throw SessionFailure(SessionProblem.INVALID_RESPONSE)
}
