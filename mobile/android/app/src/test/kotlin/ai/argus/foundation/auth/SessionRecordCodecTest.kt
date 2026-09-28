@file:OptIn(kotlin.time.ExperimentalTime::class)

package ai.argus.foundation.auth

import io.github.jan.supabase.auth.user.UserInfo
import io.github.jan.supabase.auth.user.UserSession
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Test

class SessionRecordCodecTest {
    private val original = testSession().let { value ->
        value.withSession(value.session.copy(
            providerToken = "private-provider-access",
            providerRefreshToken = "private-provider-refresh",
            user = value.session.user!!.copy(
                phone = "+15555550123",
                appMetadata = buildJsonObject { put("organization", "private-organization") },
                userMetadata = buildJsonObject { put("display_name", "Private Profile") },
            ),
        )).withRevocation(Revocation.PENDING)
    }

    @Test fun `persisted bytes contain credentials and minimal identity without profile or provider credentials`() {
        val bytes = SessionRecordCodec.encode(original)
        val json = sessionJson.parseToJsonElement(bytes.toString(Charsets.UTF_8)).jsonObject
        val session = json.getValue("session").jsonObject
        assertEquals(setOf("id", "aud"), session.getValue("user").jsonObject.keys)
        assertFalse(session.containsKey("provider_token"))
        assertFalse(session.containsKey("provider_refresh_token"))
        listOf(original.session.user!!.email!!, "+15555550123", "private-organization", "Private Profile",
            "private-provider-access", "private-provider-refresh").forEach {
            assertFalse(bytes.toString(Charsets.UTF_8).contains(it))
        }
        assertCredentials(SessionRecordCodec.decode(bytes))
    }

    @Test fun `legacy full session record remains readable while profile is discarded`() {
        val legacy = buildJsonObject {
            put("session", sessionJson.encodeToJsonElement(UserSession.serializer(), original.session))
            put("identity_id", original.identityId)
            put("kind", original.kind.name)
            put("revocation", original.revocation.name)
        }.toString().toByteArray(Charsets.UTF_8)
        assertCredentials(SessionRecordCodec.decode(legacy))
    }

    private fun assertCredentials(restored: StoredSession) {
        assertEquals(original.identityId, restored.identityId)
        assertEquals(original.kind, restored.kind)
        assertEquals(original.revocation, restored.revocation)
        assertEquals(original.session.accessToken, restored.session.accessToken)
        assertEquals(original.session.refreshToken, restored.session.refreshToken)
        assertEquals(original.session.expiresIn, restored.session.expiresIn)
        assertEquals(original.session.expiresAt, restored.session.expiresAt)
        assertEquals(original.session.tokenType, restored.session.tokenType)
        assertEquals(UserInfo(aud = original.session.user!!.aud, id = original.identityId), restored.session.user)
        assertNull(restored.session.providerToken)
        assertNull(restored.session.providerRefreshToken)
    }
}
