@file:OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)

package ai.argus.foundation.accounts

import ai.argus.foundation.auth.SessionStatus
import ai.argus.foundation.auth.SessionUiState
import java.time.ZonedDateTime
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

private class AccountsHarness(scope: TestScope) {
    val session = FakeRequests()
    val api = FakeAccountsApi()
    var nextKey = 0
    val controller = AccountsController(session, api, scope.backgroundScope,
        now = { ZonedDateTime.parse("2026-09-28T09:15:00-04:00[America/Santo_Domingo]") },
        newKey = { "request-${++nextKey}" })
}

class AccountsControllerTest {
    @Test fun uncertainCreateRetainsImmutableBodyAndKeyUntilSuccessfulReplay() = runTest {
        val h = AccountsHarness(this)
        runCurrent()
        h.controller.beginCreate()
        h.controller.updateDraft(h.controller.state.value.draft!!.copy(amount = "9,007,199,254,740.99", nickname = "Original"))
        h.api.writeFailure = AccountProblem.NETWORK
        h.controller.save()
        assertTrue(h.controller.state.value.createRetryPending)
        h.controller.updateDraft(h.controller.state.value.draft!!.copy(nickname = "Changed"))
        h.controller.save()
        assertEquals(1, h.api.creates.size)
        assertEquals("Original", h.controller.state.value.draft!!.nickname)
        h.api.writeFailure = null
        h.controller.retryCreate()
        assertEquals(2, h.api.creates.size)
        assertEquals(h.api.creates[0], h.api.creates[1])
        assertNull(h.controller.state.value.draft)
    }

    @Test fun cancellationAfterDispatchKeepsCreateIdentityForRetry() = runTest {
        val h = AccountsHarness(this)
        runCurrent()
        h.controller.beginCreate()
        h.controller.updateDraft(h.controller.state.value.draft!!.copy(amount = "0"))
        h.api.writeGate = CompletableDeferred()
        val save = launch { h.controller.save() }
        runCurrent()
        assertTrue(h.controller.state.value.createRetryPending)
        save.cancel()
        save.join()
        assertFalse(h.controller.state.value.busy)
        h.controller.save()
        assertEquals(1, h.api.creates.size)
        h.api.writeGate!!.complete(Unit)
        h.controller.retryCreate()
        assertEquals(h.api.creates[0], h.api.creates[1])
    }

    @Test fun cancelledExistingWriteRequiresRereadAndRetainsDraft() = runTest {
        val h = AccountsHarness(this)
        runCurrent()
        h.controller.open(h.api.account.id)
        h.controller.beginEdit()
        h.controller.updateDraft(h.controller.state.value.draft!!.copy(nickname = "Retained"))
        h.api.writeGate = CompletableDeferred()
        val save = launch { h.controller.save() }
        runCurrent()
        save.cancel()
        save.join()
        assertEquals("Retained", h.controller.state.value.draft!!.nickname)
        assertTrue(h.controller.state.value.reconciliationRequired)
        assertFalse(h.controller.state.value.canReconcile)
        h.controller.save()
        assertEquals(1, h.api.edits.size)
    }

    @Test fun staleMetadataRereadsButNeverSilentlyUpgradesDraftVersion() = runTest {
        val h = AccountsHarness(this)
        runCurrent()
        h.controller.open(h.api.account.id)
        h.controller.beginEdit()
        h.controller.updateDraft(h.controller.state.value.draft!!.copy(nickname = "My change", expectedVersion = 999))
        h.api.account = h.api.account.copy(version = 2, currency = "JPY")
        h.api.writeFailure = AccountProblem.STALE_VERSION
        h.controller.save()
        val state = h.controller.state.value
        assertEquals(1, state.draft!!.expectedVersion)
        assertEquals(2, state.selected!!.version)
        assertTrue(state.canReconcile)
        h.controller.save()
        assertEquals(1, h.api.edits.size)
        h.controller.reconcileDraft()
        assertEquals(2, h.controller.state.value.draft!!.expectedVersion)
        h.api.writeFailure = null
        h.controller.save()
        assertEquals("2", h.api.edits.last()["expected_version"].toString())
        assertFalse(h.api.edits.last().containsKey("currency"))
    }

    @Test fun staleUnknownOpeningBindsVersionAndNullRevisionThroughReread() = runTest {
        val h = AccountsHarness(this)
        h.api.account = fixtureAccount(known = false)
        runCurrent()
        h.controller.open(h.api.account.id)
        h.controller.beginOpening()
        h.controller.updateDraft(h.controller.state.value.draft!!.copy(amount = "100"))
        h.api.account = h.api.account.copy(version = 2, currency = "JPY", type = "credit_card", nature = "liability")
        h.api.writeFailure = AccountProblem.STALE_VERSION
        h.controller.save()
        assertEquals("1", h.api.openings.single()["expected_version"].toString())
        assertEquals("null", h.api.openings.single()["expected_revision"].toString())
        assertEquals("DOP", h.controller.state.value.draft!!.currency)
        assertEquals("JPY", h.controller.state.value.selected!!.currency)
        assertEquals("100", h.controller.state.value.draft!!.amount)
        h.controller.reconcileDraft()
        assertEquals("JPY", h.controller.state.value.draft!!.currency)
        assertEquals("credit_card", h.controller.state.value.draft!!.type)
        assertEquals("", h.controller.state.value.draft!!.amount)
        h.api.writeFailure = null
        h.controller.save()
        assertEquals(AccountProblem.AMOUNT_INVALID, h.controller.state.value.problem)
        assertEquals(1, h.api.openings.size)
        h.controller.updateDraft(h.controller.state.value.draft!!.copy(amount = "250"))
        h.controller.save()
        assertEquals("2", h.api.openings.last()["expected_version"].toString())
        assertEquals("\"250\"", h.api.openings.last()["amount"].toString())
    }

    @Test fun uncertainEditAndOpeningRequireSuccessfulRereadBeforeExplicitReconciliation() = runTest {
        listOf(DraftMode.EDIT, DraftMode.OPENING).forEach { mode ->
            val h = AccountsHarness(this)
            runCurrent()
            h.controller.open(h.api.account.id)
            if (mode == DraftMode.EDIT) h.controller.beginEdit() else h.controller.beginOpening()
            val draft = h.controller.state.value.draft!!.copy(nickname = "Preserved", reason = "Correction")
            h.controller.updateDraft(draft)
            h.api.writeFailure = AccountProblem.NETWORK
            h.api.getFailure = AccountProblem.NETWORK
            h.controller.save()
            assertEquals(draft, h.controller.state.value.draft)
            assertTrue(h.controller.state.value.reconciliationRequired)
            assertFalse(h.controller.state.value.canReconcile)
            h.controller.reconcileDraft()
            assertTrue(h.controller.state.value.reconciliationRequired)
            h.api.getFailure = null
            h.controller.open(h.api.account.id)
            assertEquals(draft, h.controller.state.value.draft)
            assertTrue(h.controller.state.value.canReconcile)
        }
    }

    @Test fun lateOldOwnerResponseAndDraftNeverEnterNewOwnerProjection() = runTest {
        val h = AccountsHarness(this)
        runCurrent()
        h.controller.beginCreate()
        h.controller.updateDraft(h.controller.state.value.draft!!.copy(nickname = "Private draft", amount = "0"))
        h.api.listGate = CompletableDeferred()
        val oldRead = launch { h.controller.refresh() }
        runCurrent()
        h.session.state.value = SessionUiState(SessionStatus.WORKING, ownershipEpoch = 2)
        runCurrent()
        assertTrue(h.controller.state.value.accounts.isEmpty())
        assertNull(h.controller.state.value.draft)
        h.api.account = fixtureAccount(id = "account-b")
        h.session.state.value = signedIn("person-b", epoch = 3)
        runCurrent()
        h.api.listGate!!.complete(Unit)
        oldRead.join()
        runCurrent()
        assertEquals(listOf("account-b"), h.controller.state.value.accounts.map { it.id })
        assertNull(h.controller.state.value.draft)
    }

    @Test fun sameOwnerRefreshPreservesDraftAndGuestRetiresIt() = runTest {
        val h = AccountsHarness(this)
        runCurrent()
        h.controller.beginCreate()
        val draft = h.controller.state.value.draft!!.copy(nickname = "Keep me")
        h.controller.updateDraft(draft)
        h.session.state.value = SessionUiState(SessionStatus.WORKING, ownershipEpoch = 1)
        runCurrent()
        h.session.state.value = signedIn()
        runCurrent()
        assertEquals(draft, h.controller.state.value.draft)
        h.session.state.value = SessionUiState(SessionStatus.GUEST_PRESERVED, ownershipEpoch = 1)
        runCurrent()
        assertNull(h.controller.state.value.draft)
        assertTrue(h.controller.state.value.accounts.isEmpty())
    }

    @Test fun validationAllowsCorrectionWithoutDiscardingDraftAndArchiveIsVersionBound() = runTest {
        val h = AccountsHarness(this)
        runCurrent()
        h.controller.beginCreate()
        h.controller.save()
        assertEquals(AccountProblem.AMOUNT_INVALID, h.controller.state.value.problem)
        assertNotNull(h.controller.state.value.draft)
        assertFalse(h.controller.state.value.createRetryPending)
        h.controller.discardDraft()
        h.controller.open(h.api.account.id)
        h.controller.beginArchive()
        h.controller.save()
        assertEquals("true", h.api.edits.single()["archived"].toString())
        assertEquals("1", h.api.edits.single()["expected_version"].toString())
    }
}
