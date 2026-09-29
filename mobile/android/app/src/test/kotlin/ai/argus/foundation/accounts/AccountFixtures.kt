package ai.argus.foundation.accounts

import ai.argus.foundation.auth.AuthenticatedRequests
import ai.argus.foundation.auth.SessionProfile
import ai.argus.foundation.auth.SessionUiState
import ai.argus.foundation.auth.SessionStatus
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.serialization.json.JsonObject

internal fun fixtureAccount(id: String = "account-a", version: Int = 1, owed: Boolean = false, known: Boolean = true): FinancialAccount {
    val amount = if (owed) "-100.00" else "9007199254740.99"
    val minor = if (owed) -10000L else 900719925474099L
    val date = "2026-09-28T09:15:00-04:00"
    val stamp = "2026-09-28T13:15:00Z"
    val revision = OpeningRevision(1, minor, amount, date, "America/Santo_Domingo", null, "person-a", stamp)
    return FinancialAccount(id, if (owed) "credit_card" else "checking", if (owed) "liability" else "asset", "DOP",
        2, "Account", false, 10000, version, stamp, stamp,
        AccountBalance(if (known) "known" else "unknown", minor.takeIf { known }, amount.takeIf { known },
            date.takeIf { known }, "opening".takeIf { known }, 0),
        AccountOpening("opening-$id", 1, minor, amount, date, revision.timeZone, null, stamp, listOf(revision)).takeIf { known })
}

internal fun signedIn(owner: String = "person-a", epoch: Long = 1) = SessionUiState(SessionStatus.SIGNED_IN,
    SessionProfile(owner, null, null, "en", "en-US"), ownershipEpoch = epoch)

internal class FakeRequests : AuthenticatedRequests {
    override val state = MutableStateFlow(signedIn())
    override suspend fun <T> authenticatedRequest(ownershipEpoch: Long, request: suspend (String) -> T) = request("synthetic-bearer")
}

internal class FakeAccountsApi : AccountsApi {
    var account = fixtureAccount()
    var listGate: CompletableDeferred<Unit>? = null
    var listFailure: AccountProblem? = null
    var getFailure: AccountProblem? = null
    var writeFailure: AccountProblem? = null
    var writeGate: CompletableDeferred<Unit>? = null
    var lists = 0
    var gets = 0
    val creates = mutableListOf<Pair<String, JsonObject>>()
    val edits = mutableListOf<JsonObject>()
    val openings = mutableListOf<JsonObject>()
    override suspend fun list(epoch: Long): List<FinancialAccount> {
        lists++
        val captured = account
        listGate?.await()
        listFailure?.let { throw AccountFailure(it) }
        return listOf(captured)
    }
    override suspend fun get(epoch: Long, id: String): FinancialAccount {
        gets++
        getFailure?.let { throw AccountFailure(it) }
        return account
    }
    private suspend fun write(): FinancialAccount {
        writeGate?.await()
        writeFailure?.let { throw AccountFailure(it) }
        return account
    }
    override suspend fun create(epoch: Long, key: String, payload: JsonObject): FinancialAccount {
        creates += key to payload
        return write()
    }
    override suspend fun edit(epoch: Long, id: String, payload: JsonObject): FinancialAccount {
        edits += payload
        return write()
    }
    override suspend fun opening(epoch: Long, id: String, payload: JsonObject): FinancialAccount {
        openings += payload
        return write()
    }
}
