package ai.argus.foundation.accounts

/** Server-owned facts. Decimal strings and Long minor units never pass through Double. */
data class FinancialAccount(
    val id: String,
    val type: String,
    val nature: String,
    val currency: String,
    val currencyFractionDigits: Int,
    val nickname: String?,
    val archived: Boolean,
    val ownershipShareBps: Int,
    val version: Int,
    val createdAt: String,
    val updatedAt: String,
    val balance: AccountBalance,
    val opening: AccountOpening?,
)

data class AccountBalance(
    val state: String,
    val amountMinor: Long?,
    val amount: String?,
    val asOf: String?,
    val basis: String?,
    val activitySinceTrackingMinor: Long,
)

data class OpeningRevision(
    val revision: Int,
    val amountMinor: Long,
    val amount: String,
    val asOf: String,
    val timeZone: String,
    val reason: String?,
    val recordedBy: String?,
    val recordedAt: String,
)

data class AccountOpening(
    val recordId: String,
    val revision: Int,
    val amountMinor: Long,
    val amount: String,
    val asOf: String,
    val timeZone: String,
    val reason: String?,
    val recordedAt: String,
    val revisions: List<OpeningRevision>,
)

enum class DraftMode { CREATE, EDIT, OPENING, ARCHIVE }

data class AccountDraft(
    val mode: DraftMode = DraftMode.CREATE,
    val accountId: String? = null,
    val expectedVersion: Int? = null,
    val expectedRevision: Int? = null,
    val type: String = "checking",
    val currency: String = "DOP",
    val nature: String? = null,
    val nickname: String = "",
    val amount: String = "",
    val balanceKnown: Boolean = true,
    val asOf: String = "",
    val timeZone: String = "",
    val reason: String = "",
    val ownershipPercent: String = "100",
    val archived: Boolean = false,
    val localeTag: String = "en",
)

enum class AccountProblem {
    UNAVAILABLE, REGISTRATION_REQUIRED, NOT_FOUND, AUTH_REQUIRED,
    STALE_VERSION, IDEMPOTENCY_CONFLICT, VALIDATION,
    AMOUNT_INVALID, AMOUNT_PRECISION, AMOUNT_OUT_OF_RANGE,
    CURRENCY_UNSUPPORTED, CURRENCY_LOCKED, TYPE_LOCKED, NATURE_CHANGE_REQUIRES_EMPTY_ACCOUNT,
    DATE_INVALID, DATE_IN_FUTURE, TIME_ZONE_INVALID, NICKNAME_INVALID,
    OWNERSHIP_SHARE_INVALID, REASON_REQUIRED, REASON_INVALID, FIELD_MISSING,
    NETWORK, SERVER, INVALID_RESPONSE,
}

data class AccountsUiState(
    val accounts: List<FinancialAccount> = emptyList(),
    val selected: FinancialAccount? = null,
    val draft: AccountDraft? = null,
    val busy: Boolean = false,
    val problem: AccountProblem? = null,
    val reconciliationRequired: Boolean = false,
    val canReconcile: Boolean = false,
    val createRetryPending: Boolean = false,
    val ownershipEpoch: Long = 0,
    val loaded: Boolean = false,
)

/** Error text is a finite client enum, never a server detail or exception payload. */
internal class AccountFailure(val problem: AccountProblem) : Exception(problem.name)
