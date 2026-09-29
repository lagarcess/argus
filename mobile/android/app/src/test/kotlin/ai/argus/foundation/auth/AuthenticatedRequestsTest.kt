@file:OptIn(kotlin.time.ExperimentalTime::class, kotlinx.coroutines.ExperimentalCoroutinesApi::class)

package ai.argus.foundation.auth

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

class AuthenticatedRequestsTest {
    @Test fun rejectedRequestUsesOwnedRefreshButNeverReplaysMutation() = runTest {
        val sdk = FakeSdk()
        val controller = SessionController(FakeBackend(), FakeVault(testSession()), sdk, StandardTestDispatcher(testScheduler)) { testNow }
        controller.restore()
        var calls = 0
        try {
            controller.authenticatedRequest(controller.state.value.ownershipEpoch) {
                calls++
                throw BearerRejected()
            }
            fail("Expected explicit retry through the caller")
        } catch (_: SessionAccessFailure) { }
        assertEquals(1, calls)
        assertEquals(1, sdk.refreshCalls)
        assertEquals(SessionStatus.SIGNED_IN, controller.state.value.status)
    }

    @Test fun lateResponseAfterSignOutCannotReturnPrivateData() = runTest {
        val controller = SessionController(FakeBackend(), FakeVault(testSession()), FakeSdk(), StandardTestDispatcher(testScheduler)) { testNow }
        controller.restore()
        val gate = CompletableDeferred<Unit>()
        var returned = false
        val read = launch {
            try {
                controller.authenticatedRequest(controller.state.value.ownershipEpoch) { gate.await(); "private result" }
                returned = true
            } catch (_: SessionAccessFailure) { }
        }
        runCurrent()
        val signOut = launch { controller.signOut() }
        runCurrent()
        gate.complete(Unit)
        read.join()
        signOut.join()
        assertFalse(returned)
        assertEquals(SessionStatus.SIGNED_OUT, controller.state.value.status)
    }

    @Test fun failedRefreshRetiresAccessThroughExistingRejectionPath() = runTest {
        val sdk = FakeSdk().apply { refreshFailure = SessionProblem.REJECTED_SESSION }
        val vault = FakeVault(testSession())
        val controller = SessionController(FakeBackend(), vault, sdk, StandardTestDispatcher(testScheduler)) { testNow }
        controller.restore()
        try {
            controller.authenticatedRequest(controller.state.value.ownershipEpoch) { throw BearerRejected() }
            fail("Expected no access")
        } catch (_: SessionAccessFailure) { }
        assertEquals(SessionStatus.SIGNED_OUT, controller.state.value.status)
        assertNull(vault.value)
    }
}
