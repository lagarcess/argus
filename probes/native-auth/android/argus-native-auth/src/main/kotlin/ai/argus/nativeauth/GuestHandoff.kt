package ai.argus.nativeauth

import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonPrimitive

enum class HandoffTransport { SCOPED_COOKIES, HEADER }

@Serializable
data class StoredHandoff(val id: String, val secret: String)

/** The guest handoff credential. Sent only on /auth/ paths, deleted when Argus finishes it. */
class HandoffStore(private val store: SecureStore, val transport: HandoffTransport) {
    private val key = "guest-handoff"
    private val cookieNames = setOf("argus-guest-handoff", "argus-guest-handoff-id")

    val current: StoredHandoff?
        get() = store.get(key)?.let { Json.decodeFromString<StoredHandoff>(it) }

    fun headers(path: String): Map<String, String> {
        if (!path.startsWith("/auth/")) return emptyMap()
        val handoff = current
        return when (transport) {
            HandoffTransport.SCOPED_COOKIES ->
                handoff?.let { mapOf("Cookie" to "argus-guest-handoff=${it.secret}; argus-guest-handoff-id=${it.id}") }
                    ?: emptyMap()
            HandoffTransport.HEADER -> buildMap {
                put("Argus-Guest-Handoff-Transport", "header")
                handoff?.let {
                    put("Argus-Guest-Handoff-Id", it.id)
                    put("Argus-Guest-Handoff-Secret", it.secret)
                }
            }
        }
    }

    fun absorb(response: ApiResponse) {
        when (transport) {
            HandoffTransport.SCOPED_COOKIES -> {
                val cookies = response.setCookies.filter { it.name in cookieNames }
                if (cookies.isEmpty()) return
                if (cookies.any { it.expiresAt <= System.currentTimeMillis() || it.value.isEmpty() }) {
                    return store.remove(key)
                }
                val secret = cookies.firstOrNull { it.name == "argus-guest-handoff" }?.value
                val id = cookies.firstOrNull { it.name == "argus-guest-handoff-id" }?.value
                if (secret != null && id != null) save(StoredHandoff(id, secret))
            }
            HandoffTransport.HEADER -> {
                if (response.headers["argus-guest-handoff-state"] == "cleared") return store.remove(key)
                val secret = response.body["handoff_secret"]?.jsonPrimitive?.content
                val id = response.body["handoff_id"]?.jsonPrimitive?.content
                if (secret != null && id != null) save(StoredHandoff(id, secret))
            }
        }
    }

    fun clear() = store.remove(key)

    private fun save(handoff: StoredHandoff) = store.put(key, Json.encodeToString(handoff))
}
