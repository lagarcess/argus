@file:OptIn(kotlin.time.ExperimentalTime::class, kotlinx.coroutines.ExperimentalCoroutinesApi::class)

package ai.argus.foundation.auth

import io.github.jan.supabase.auth.user.UserInfo
import io.github.jan.supabase.auth.user.UserSession
import java.util.Base64
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.time.Instant

internal val testNow = Instant.parse("2026-09-28T12:00:00Z")

internal fun testSession(id: String = "account-a", token: String = "synthetic-access-$id", expired: Boolean = false): StoredSession = StoredSession(
    UserSession(token, "synthetic-refresh-$id", expiresIn = 3600, tokenType = "bearer",
        user = UserInfo(aud = "authenticated", id = id, email = "$id@example.test"),
        expiresAt = Instant.parse(if (expired) "2026-09-28T11:00:00Z" else "2026-09-28T13:00:00Z")),
    id, AccountKind.REGISTERED,
)

internal class FakeVault(var value: StoredSession? = null) : SessionVault {
    var failure: SessionProblem? = null
    var clearFailure = false
    var saves = 0
    override suspend fun load(): StoredSession? {
        failure?.let { throw SessionFailure(it) }
        return value
    }
    override suspend fun save(value: StoredSession) {
        failure?.let { throw SessionFailure(it) }
        saves++
        this.value = value
    }
    override suspend fun clear() {
        if (clearFailure) throw SessionFailure(SessionProblem.STORAGE)
        value = null
    }
}

internal class FakeBackend : SessionBackend {
    var meFailure: SessionProblem? = null
    var meGate: CompletableDeferred<Unit>? = null
    var loginGate: CompletableDeferred<Unit>? = null
    var loginResult = testSession()
    var meId = "account-a"
    var kind = AccountKind.REGISTERED
    var loginCalls = 0
    var meCalls = 0
    override suspend fun signIn(email: String, password: String): StoredSession {
        loginCalls++
        loginGate?.await()
        return loginResult
    }
    override suspend fun me(accessToken: String): VerifiedAccount {
        meCalls++
        meGate?.await()
        meFailure?.let { throw SessionFailure(it) }
        return VerifiedAccount(kind, SessionProfile(meId, "$meId@example.test", "Verified $meId", "en", "en-US"))
    }
}

internal class FakeSdk : SessionSdk {
    var refreshGate: CompletableDeferred<Unit>? = null
    var refreshFailure: SessionProblem? = null
    var revokeFailure: SessionProblem? = null
    var refreshResult = testSession(token = "rotated-access").session
    var refreshCalls = 0
    var revokeCalls = 0
    var imports = 0
    override suspend fun importSession(session: UserSession) { imports++ }
    override suspend fun refresh(session: UserSession): UserSession {
        refreshCalls++
        refreshGate?.await()
        refreshFailure?.let { throw SessionFailure(it) }
        return refreshResult
    }
    override suspend fun revoke(session: UserSession) {
        revokeCalls++
        revokeFailure?.let { throw SessionFailure(it) }
    }
    override suspend fun clear() = Unit
}

private class Harness(scope: TestScope, initial: StoredSession? = testSession()) {
    val backend = FakeBackend()
    val vault = FakeVault(initial)
    val sdk = FakeSdk()
    val controller = SessionController(backend, vault, sdk, StandardTestDispatcher(scope.testScheduler)) { testNow }
}

class SessionControllerTest {
    @Test fun profileAppearsOnlyAfterBearerVerification() = runTest {
        val h = Harness(this, initial = null)
        h.controller.restore()
        h.backend.meGate = CompletableDeferred()
        val login = launch { h.controller.signIn("account-a@example.test", "synthetic-password") }
        runCurrent()
        assertEquals(SessionStatus.WORKING, h.controller.state.value.status)
        assertNull(h.controller.state.value.profile)
        h.backend.meGate!!.complete(Unit)
        login.join()
        assertEquals("Verified account-a", h.controller.state.value.profile?.displayName)
        assertEquals(1, h.sdk.imports)
    }

    @Test fun transientRestorePreservesCredentialsWithoutShowingPrivateProfile() = runTest {
        listOf(SessionProblem.NETWORK, SessionProblem.VERIFICATION_UNAVAILABLE).forEach { failure ->
            val original = testSession()
            val h = Harness(this, original)
            h.backend.meFailure = failure
            h.controller.restore()
            assertEquals(SessionStatus.RECOVERY_REQUIRED, h.controller.state.value.status)
            assertNull(h.controller.state.value.profile)
            assertSame(original, h.vault.value)
            h.backend.meFailure = null
            h.controller.retry()
            assertEquals(SessionStatus.SIGNED_IN, h.controller.state.value.status)
        }
    }

    @Test fun explicitSessionRejectionClearsInvalidCredentials() = runTest {
        val h = Harness(this)
        h.backend.meFailure = SessionProblem.REJECTED_SESSION
        h.controller.restore()
        assertEquals(SessionStatus.SIGNED_OUT, h.controller.state.value.status)
        assertEquals(SessionProblem.REJECTED_SESSION, h.controller.state.value.problem)
        assertNull(h.vault.value)
        assertNull(h.controller.state.value.profile)
    }

    @Test fun lateProfileResponseCannotRepopulateUiAfterSignOutBegins() = runTest {
        val h = Harness(this)
        h.backend.meGate = CompletableDeferred()
        val restore = launch { h.controller.restore() }
        runCurrent()
        val logout = launch { h.controller.signOut() }
        runCurrent()
        assertNull(h.controller.state.value.profile)
        h.backend.meGate!!.complete(Unit)
        restore.join()
        logout.join()
        assertEquals(SessionStatus.SIGNED_OUT, h.controller.state.value.status)
        assertNull(h.controller.state.value.profile)
        assertNull(h.vault.value)
        assertEquals(0, h.sdk.imports)
    }

    @Test fun lateLoginIsRetainedOnlyLongEnoughToCompleteRequestedRevocation() = runTest {
        val h = Harness(this, null)
        h.controller.restore()
        h.backend.loginGate = CompletableDeferred()
        val login = launch { h.controller.signIn("account-a@example.test", "synthetic") }
        runCurrent()
        val logout = launch { h.controller.signOut() }
        runCurrent()
        h.backend.loginGate!!.complete(Unit)
        login.join()
        logout.join()
        assertEquals(1, h.sdk.revokeCalls)
        assertEquals(0, h.backend.meCalls)
        assertEquals(SessionStatus.SIGNED_OUT, h.controller.state.value.status)
    }

    @Test fun concurrentRefreshesMakeOneProviderRequestAndKeepIdentity() = runTest {
        val h = Harness(this)
        h.controller.restore()
        val ownerEpoch = h.controller.state.value.ownershipEpoch
        h.sdk.refreshGate = CompletableDeferred()
        val refreshes = List(8) { async { h.controller.refresh() } }
        runCurrent()
        assertEquals(1, h.sdk.refreshCalls)
        h.sdk.refreshGate!!.complete(Unit)
        refreshes.forEach { it.await() }
        assertEquals(1, h.sdk.refreshCalls)
        assertEquals("account-a", h.controller.state.value.profile?.id)
        assertEquals(ownerEpoch, h.controller.state.value.ownershipEpoch)
        assertEquals("rotated-access", h.vault.value?.session?.accessToken)
    }

    @Test fun refreshedIdentityMismatchCannotReplaceTheOriginalOwner() = runTest {
        val h = Harness(this)
        h.controller.restore()
        h.sdk.refreshResult = testSession("account-b").session
        h.controller.refresh()
        assertEquals(SessionProblem.INVALID_RESPONSE, h.controller.state.value.problem)
        assertEquals("account-a", h.vault.value?.identityId)
        assertEquals("synthetic-access-account-a", h.vault.value?.session?.accessToken)
        assertNull(h.controller.state.value.profile)
    }

    @Test fun failedRevocationRetiresProfileAndBlocksAccountSwitchUntilRetrySucceeds() = runTest {
        val h = Harness(this)
        h.controller.restore()
        val ownerEpoch = h.controller.state.value.ownershipEpoch
        h.sdk.revokeFailure = SessionProblem.REVOCATION
        h.controller.signOut()
        assertEquals(SessionStatus.REVOCATION_FAILED, h.controller.state.value.status)
        assertNull(h.controller.state.value.profile)
        assertTrue(h.controller.state.value.ownershipEpoch > ownerEpoch)
        assertEquals(Revocation.PENDING, h.vault.value?.revocation)
        h.controller.signIn("account-b@example.test", "new-password")
        assertEquals(0, h.backend.loginCalls)
        h.sdk.revokeFailure = null
        h.controller.retry()
        h.backend.loginResult = testSession("account-b")
        h.backend.meId = "account-b"
        h.controller.signIn("account-b@example.test", "new-password")
        assertEquals("account-b", h.controller.state.value.profile?.id)
    }

    @Test fun relaunchAfterUnfinishedRevocationNeverHydratesPrivateProfile() = runTest {
        val h = Harness(this, testSession().withRevocation(Revocation.PENDING))
        h.controller.restore()
        assertEquals(SessionStatus.REVOCATION_FAILED, h.controller.state.value.status)
        assertEquals(0, h.backend.meCalls)
        h.controller.retry()
        assertEquals(SessionStatus.SIGNED_OUT, h.controller.state.value.status)
    }

    @Test fun confirmedRevocationCanRetryLocalDeletionWithoutRepeatingRemoteLogout() = runTest {
        val h = Harness(this)
        h.controller.restore()
        h.vault.clearFailure = true
        h.controller.signOut()
        assertEquals(SessionStatus.REVOCATION_FAILED, h.controller.state.value.status)
        assertEquals(Revocation.CONFIRMED, h.vault.value?.revocation)
        h.vault.clearFailure = false
        h.controller.retry()
        assertEquals(1, h.sdk.revokeCalls)
        assertEquals(SessionStatus.SIGNED_OUT, h.controller.state.value.status)
    }

    @Test fun rejectedRefreshAfterUnconfirmedRevocationClearsInvalidSessionWithoutClaimingRevocation() = runTest {
        listOf(false, true).forEach { expired ->
            val h = Harness(this, testSession(expired = expired).withRevocation(Revocation.PENDING))
            h.sdk.refreshFailure = SessionProblem.REJECTED_SESSION
            h.controller.restore()
            h.controller.retry()
            assertEquals(SessionStatus.SIGNED_OUT, h.controller.state.value.status)
            assertEquals(SessionProblem.REJECTED_SESSION, h.controller.state.value.problem)
            assertNull(h.vault.value)
            assertEquals(0, h.sdk.revokeCalls)
            assertEquals(1, h.sdk.refreshCalls)
        }
    }

    @Test fun guestsArePreservedWithoutRefreshLoginOrSignOutMutation() = runTest {
        val payload = Base64.getUrlEncoder().withoutPadding().encodeToString("{\"is_anonymous\":true}".toByteArray())
        val guestRecords = listOf(
            testSession(expired = true).withKind(AccountKind.GUEST),
            testSession(token = "header.$payload.signature", expired = true).withKind(AccountKind.UNKNOWN),
        )
        guestRecords.forEach { guest ->
            val h = Harness(this, guest)
            h.controller.restore()
            h.controller.signIn("other@example.test", "synthetic")
            h.controller.refresh()
            h.controller.signOut()
            assertEquals(SessionStatus.GUEST_PRESERVED, h.controller.state.value.status)
            assertSame(guest, h.vault.value)
            assertEquals(0, h.vault.saves)
            assertEquals(0, h.sdk.refreshCalls)
            assertEquals(0, h.sdk.revokeCalls)
            assertEquals(0, h.backend.loginCalls)
        }
    }

    @Test fun unreadableStorageDoesNotBecomePermissionToOverwriteIt() = runTest {
        val h = Harness(this)
        h.vault.failure = SessionProblem.STORAGE
        h.controller.restore()
        h.controller.signIn("other@example.test", "synthetic")
        assertEquals(SessionStatus.RECOVERY_REQUIRED, h.controller.state.value.status)
        assertEquals(0, h.backend.loginCalls)
        assertTrue(h.vault.value != null)
    }

    @Test fun duplicateForegroundRestoresCoalesceAndExpiredSessionsRefreshBeforeMe() = runTest {
        val h = Harness(this, testSession(expired = true))
        h.sdk.refreshGate = CompletableDeferred()
        repeat(5) { launch { h.controller.restore() } }
        runCurrent()
        assertEquals(1, h.sdk.refreshCalls)
        assertEquals(0, h.backend.meCalls)
        h.sdk.refreshGate!!.complete(Unit)
        advanceUntilIdle()
        assertEquals(1, h.backend.meCalls)
        assertEquals(SessionStatus.SIGNED_IN, h.controller.state.value.status)
    }
}
