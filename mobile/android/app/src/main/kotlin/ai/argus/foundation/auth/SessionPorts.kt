package ai.argus.foundation.auth

import io.github.jan.supabase.auth.user.UserSession

internal enum class AccountKind { UNKNOWN, REGISTERED, GUEST }
internal enum class Revocation { NONE, PENDING, CONFIRMED }

/** Credentials stay inside the auth boundary; this class deliberately has no generated toString. */
internal class StoredSession(
    val session: UserSession,
    val identityId: String,
    val kind: AccountKind = AccountKind.UNKNOWN,
    val revocation: Revocation = Revocation.NONE,
) {
    fun withSession(value: UserSession) = StoredSession(value, identityId, kind, revocation)
    fun withKind(value: AccountKind) = StoredSession(session, identityId, value, revocation)
    fun withRevocation(value: Revocation) = StoredSession(session, identityId, kind, value)
    override fun toString(): String = "StoredSession(<redacted>)"
}

internal class VerifiedAccount(val kind: AccountKind, val profile: SessionProfile)

internal interface SessionBackend {
    suspend fun signIn(email: String, password: String): StoredSession
    suspend fun me(accessToken: String): VerifiedAccount
}

internal interface SessionVault {
    suspend fun load(): StoredSession?
    suspend fun save(value: StoredSession)
    suspend fun clear()
}

internal interface SessionSdk {
    suspend fun importSession(session: UserSession)
    suspend fun refresh(session: UserSession): UserSession
    suspend fun revoke(session: UserSession)
    suspend fun clear()
}
