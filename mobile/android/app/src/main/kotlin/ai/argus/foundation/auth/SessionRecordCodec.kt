@file:OptIn(kotlin.time.ExperimentalTime::class)

package ai.argus.foundation.auth

import io.github.jan.supabase.auth.user.UserInfo
import io.github.jan.supabase.auth.user.UserSession
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put

/** Explicitly select durable auth fields; SDK profile additions cannot enter the vault. */
internal object SessionRecordCodec {
    fun encode(value: StoredSession): ByteArray = buildJsonObject {
        put("session", sessionJson.encodeToJsonElement(UserSession.serializer(), credentials(value.session)))
        put("identity_id", value.identityId)
        put("kind", value.kind.name)
        put("revocation", value.revocation.name)
    }.toString().toByteArray(Charsets.UTF_8)

    fun decode(bytes: ByteArray): StoredSession {
        val json = sessionJson.parseToJsonElement(bytes.toString(Charsets.UTF_8)).jsonObject
        val session = sessionJson.decodeFromJsonElement(UserSession.serializer(), json.getValue("session"))
        val id = requireNotNull(json.string("identity_id"))
        require(id.isNotBlank() && session.user?.id == id)
        require(session.accessToken.isNotBlank() && session.refreshToken.isNotBlank())
        // Existing encrypted records remain readable, but their profile is discarded too.
        return StoredSession(credentials(session), id,
            AccountKind.valueOf(requireNotNull(json.string("kind"))),
            Revocation.valueOf(requireNotNull(json.string("revocation"))))
    }

    private fun credentials(session: UserSession) = UserSession(
        accessToken = session.accessToken,
        refreshToken = session.refreshToken,
        expiresIn = session.expiresIn,
        tokenType = session.tokenType,
        expiresAt = session.expiresAt,
        user = session.user?.let { UserInfo(aud = it.aud, id = it.id) },
    )
}
