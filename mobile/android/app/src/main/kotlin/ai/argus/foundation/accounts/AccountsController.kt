package ai.argus.foundation.accounts

import ai.argus.foundation.auth.AuthenticatedRequests
import ai.argus.foundation.auth.SessionStatus
import java.math.BigDecimal
import java.time.ZonedDateTime
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.serialization.json.JsonObject

/** A memory-only projection, scoped to the single registered session owner. */
class AccountsController internal constructor(
    private val session: AuthenticatedRequests,
    private val api: AccountsApi,
    private val scope: CoroutineScope,
    private val now: () -> ZonedDateTime = { ZonedDateTime.now() },
    private val newKey: () -> String = { UUID.randomUUID().toString() },
) {
    private val mutableState = MutableStateFlow(AccountsUiState())
    val state: StateFlow<AccountsUiState> = mutableState.asStateFlow()
    private val operation = Mutex()
    private var owner: String? = null
    private var originalDraft: AccountDraft? = null
    private var pendingCreate: PendingCreate? = null
    private data class PendingCreate(val key: String, val body: JsonObject)

    init {
        scope.launch(start = CoroutineStart.UNDISPATCHED) {
            session.state.collect { auth ->
                val retired = auth.ownershipEpoch != state.value.ownershipEpoch ||
                    auth.status in setOf(SessionStatus.SIGNED_OUT, SessionStatus.GUEST_PRESERVED, SessionStatus.DISABLED,
                        SessionStatus.REVOCATION_FAILED) ||
                    (auth.status == SessionStatus.SIGNED_IN && auth.profile?.id != owner)
                if (retired) {
                    owner = null
                    originalDraft = null
                    pendingCreate = null
                    mutableState.value = AccountsUiState(ownershipEpoch = auth.ownershipEpoch)
                }
                if (auth.status == SessionStatus.SIGNED_IN && auth.profile != null && owner == null) {
                    owner = auth.profile.id
                    scope.launch { refresh() }
                }
            }
        }
    }

    suspend fun refresh() = run {
        val accounts = api.list(it)
        publish(it) { current -> current.copy(accounts = accounts, loaded = true,
            selected = current.selected?.let { selected -> accounts.find { account -> account.id == selected.id } }) }
    }

    suspend fun open(id: String) = run { epoch ->
        val account = api.get(epoch, id)
        publish(epoch) { current ->
            val retainingDraft = current.reconciliationRequired && current.draft?.accountId == id
            if (!retainingDraft) { originalDraft = null; pendingCreate = null }
            current.copy(selected = account, accounts = replace(current.accounts, account),
                draft = current.draft.takeIf { retainingDraft },
                reconciliationRequired = retainingDraft, canReconcile = retainingDraft)
        }
    }

    fun showList() {
        if (!editable()) return
        discardDraft()
        mutableState.value = state.value.copy(selected = null, problem = null)
    }

    fun beginCreate(localeTag: String = "en") {
        if (!editable()) return
        setDraft(AccountDraft(localeTag = localeTag))
    }
    fun beginEdit(localeTag: String = "en") = begin(DraftMode.EDIT, localeTag)
    fun beginOpening(localeTag: String = "en") = begin(DraftMode.OPENING, localeTag)
    fun beginArchive() = begin(DraftMode.ARCHIVE, "en")

    private fun begin(mode: DraftMode, localeTag: String) {
        if (!editable()) return
        val account = state.value.selected ?: return
        val date = now()
        setDraft(AccountDraft(mode = mode, accountId = account.id, expectedVersion = account.version,
            expectedRevision = account.opening?.revision, type = account.type, currency = account.currency, nature = account.nature,
            nickname = account.nickname.orEmpty(), amount = openingInput(account, localeTag),
            balanceKnown = account.balance.state == "known",
            asOf = account.opening?.asOf ?: date.toOffsetDateTime().toString(),
            timeZone = account.opening?.timeZone ?: date.zone.id,
            ownershipPercent = formatAccountAmount(BigDecimal(account.ownershipShareBps).movePointLeft(2)
                .stripTrailingZeros().toPlainString(), localeTag),
            archived = if (mode == DraftMode.ARCHIVE) !account.archived else account.archived, localeTag = localeTag))
    }

    private fun setDraft(draft: AccountDraft) {
        originalDraft = draft
        pendingCreate = null
        mutableState.value = state.value.copy(draft = draft, problem = null, reconciliationRequired = false,
            canReconcile = false, createRetryPending = false)
    }

    fun updateDraft(value: AccountDraft) {
        if (!editable() || state.value.createRetryPending) return
        val current = state.value.draft ?: return
        // The snapshot binding belongs to this owner, never to freely editable form fields.
        mutableState.value = state.value.copy(draft = value.copy(mode = current.mode, accountId = current.accountId,
            expectedVersion = current.expectedVersion, expectedRevision = current.expectedRevision,
            localeTag = current.localeTag, nature = current.nature), problem = null)
    }

    fun discardDraft() {
        if (!editable()) return
        originalDraft = null
        pendingCreate = null
        mutableState.value = state.value.copy(draft = null, problem = null, reconciliationRequired = false,
            canReconcile = false, createRetryPending = false)
    }

    /** Explicit user action after seeing current server truth; save remains a separate action. */
    suspend fun reconcileDraft() {
        if (!editable() || !state.value.canReconcile) return
        val draft = state.value.draft ?: return
        val current = state.value.selected?.takeIf { it.id == draft.accountId } ?: return
        val previous = originalDraft ?: return
        val latest = draft.copy(expectedVersion = current.version, expectedRevision = current.opening?.revision,
            currency = current.currency, type = current.type, nature = current.nature, nickname = current.nickname.orEmpty(),
            amount = openingInput(current, draft.localeTag), balanceKnown = current.balance.state == "known",
            asOf = current.opening?.asOf ?: previous.asOf, timeZone = current.opening?.timeZone ?: previous.timeZone,
            ownershipPercent = formatAccountAmount(BigDecimal(current.ownershipShareBps).movePointLeft(2)
                .stripTrailingZeros().toPlainString(), draft.localeTag))
        // Rebase only after consent. Unchanged fields follow current facts; explicit edits retain intent.
        val reconciled = latest.copy(
            nickname = if (draft.nickname != previous.nickname) draft.nickname else latest.nickname,
            type = if (draft.mode == DraftMode.EDIT && draft.type != previous.type) draft.type else latest.type,
            currency = if (draft.mode == DraftMode.EDIT && draft.currency != previous.currency) draft.currency else latest.currency,
            amount = if (parseAccountAmount(draft.amount, draft.localeTag) !=
                parseAccountAmount(previous.amount, previous.localeTag)) draft.amount else latest.amount,
            asOf = if (draft.asOf != previous.asOf) draft.asOf else latest.asOf,
            timeZone = if (draft.timeZone != previous.timeZone) draft.timeZone else latest.timeZone,
            ownershipPercent = if (draft.ownershipPercent != previous.ownershipPercent) draft.ownershipPercent else latest.ownershipPercent)
        val basisChanged = draft.mode == DraftMode.OPENING &&
            (previous.currency != current.currency || previous.nature != current.nature)
        // A number typed under a different currency/nature needs deliberate input under the new label.
        val accepted = if (basisChanged) reconciled.copy(amount = "") else reconciled
        originalDraft = latest
        mutableState.value = state.value.copy(draft = accepted, reconciliationRequired = false,
            canReconcile = false, problem = null)
    }

    suspend fun save() {
        if (state.value.reconciliationRequired || state.value.createRetryPending) return
        val draft = state.value.draft ?: return
        val original = originalDraft ?: return
        run { epoch ->
            val body = draftPayload(draft, original)
            if (draft.mode == DraftMode.CREATE) {
                val pending = PendingCreate(newKey(), body)
                pendingCreate = pending
                create(epoch, pending)
            } else {
                try {
                    val id = requireNotNull(draft.accountId)
                    val saved = if (draft.mode == DraftMode.OPENING) api.opening(epoch, id, body) else api.edit(epoch, id, body)
                    saved(epoch, saved)
                } catch (cancelled: CancellationException) {
                    publish(epoch) { it.copy(reconciliationRequired = true, canReconcile = false,
                        problem = AccountProblem.NETWORK) }
                    throw cancelled
                } catch (failure: AccountFailure) {
                    if (failure.problem in reconcileProblems) reread(epoch, requireNotNull(draft.accountId), failure.problem)
                    else throw failure
                }
            }
        }
    }

    suspend fun retryCreate() {
        val pending = pendingCreate ?: return
        if (!state.value.createRetryPending) return
        run { create(it, pending) }
    }

    private suspend fun create(epoch: Long, pending: PendingCreate) {
        // Freeze identity before dispatch, including cancellation while the server may commit.
        publish(epoch) { it.copy(createRetryPending = true) }
        try { saved(epoch, api.create(epoch, pending.key, pending.body)) }
        catch (cancelled: CancellationException) {
            publish(epoch) { it.copy(problem = AccountProblem.NETWORK) }
            throw cancelled
        } catch (failure: AccountFailure) {
            publish(epoch) { current ->
                val uncertain = failure.problem in uncertainProblems
                if (!uncertain) pendingCreate = null
                current.copy(createRetryPending = uncertain, problem = failure.problem)
            }
        }
    }

    private suspend fun reread(epoch: Long, id: String, problem: AccountProblem) {
        publish(epoch) { it.copy(reconciliationRequired = true, canReconcile = false, problem = problem) }
        try {
            val current = api.get(epoch, id)
            publish(epoch) { it.copy(selected = current, accounts = replace(it.accounts, current), canReconcile = true) }
        } catch (_: AccountFailure) {
            // Keep the original write failure and draft. An explicit reread can recover later.
        }
    }

    private fun saved(epoch: Long, account: FinancialAccount) = publish(epoch) {
        originalDraft = null
        pendingCreate = null
        it.copy(accounts = replace(it.accounts, account), selected = account, draft = null,
            reconciliationRequired = false, canReconcile = false, createRetryPending = false, problem = null)
    }

    private suspend fun run(block: suspend (Long) -> Unit) {
        if (!editable() || !operation.tryLock()) return
        val epoch = session.state.value.ownershipEpoch
        publish(epoch) { it.copy(busy = true, problem = null) }
        try { block(epoch) }
        catch (failure: AccountFailure) { publish(epoch) { it.copy(problem = failure.problem) } }
        finally {
            if (state.value.ownershipEpoch == epoch) mutableState.value = state.value.copy(busy = false)
            operation.unlock()
            if (session.state.value.ownershipEpoch != epoch && !state.value.loaded) scope.launch { refresh() }
        }
    }

    private fun editable() = !state.value.busy && session.state.value.status == SessionStatus.SIGNED_IN &&
        owner != null && session.state.value.profile?.id == owner &&
        session.state.value.ownershipEpoch == state.value.ownershipEpoch

    private fun publish(epoch: Long, change: (AccountsUiState) -> AccountsUiState) {
        val auth = session.state.value
        if (epoch == auth.ownershipEpoch && epoch == state.value.ownershipEpoch && auth.profile?.id == owner &&
            auth.status == SessionStatus.SIGNED_IN && owner != null) mutableState.value = change(state.value)
    }

    private fun replace(accounts: List<FinancialAccount>, account: FinancialAccount) =
        if (accounts.any { it.id == account.id }) accounts.map { if (it.id == account.id) account else it }
        else accounts + account

    private companion object {
        val uncertainProblems = setOf(AccountProblem.NETWORK, AccountProblem.SERVER, AccountProblem.INVALID_RESPONSE)
        val reconcileProblems = uncertainProblems + setOf(AccountProblem.STALE_VERSION, AccountProblem.AUTH_REQUIRED)
    }
}
