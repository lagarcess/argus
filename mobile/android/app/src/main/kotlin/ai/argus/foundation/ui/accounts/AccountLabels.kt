package ai.argus.foundation.ui.accounts

import ai.argus.foundation.R

internal val accountTypeLabels = linkedMapOf(
    "cash" to R.string.account_type_cash,
    "checking" to R.string.account_type_checking,
    "savings" to R.string.account_type_savings,
    "investment" to R.string.account_type_investment,
    "credit_card" to R.string.account_type_credit_card,
    "other_debt" to R.string.account_type_other_debt,
    "property" to R.string.account_type_property,
    "vehicle" to R.string.account_type_vehicle,
    "other_asset" to R.string.account_type_other_asset,
)

internal fun accountProblemLabel(problem: ai.argus.foundation.accounts.AccountProblem): Int = when (problem) {
    ai.argus.foundation.accounts.AccountProblem.UNAVAILABLE -> R.string.account_error_unavailable
    ai.argus.foundation.accounts.AccountProblem.REGISTRATION_REQUIRED -> R.string.account_guest_required
    ai.argus.foundation.accounts.AccountProblem.NOT_FOUND -> R.string.account_error_not_found
    ai.argus.foundation.accounts.AccountProblem.AUTH_REQUIRED -> R.string.account_error_auth
    ai.argus.foundation.accounts.AccountProblem.STALE_VERSION -> R.string.account_error_stale
    ai.argus.foundation.accounts.AccountProblem.IDEMPOTENCY_CONFLICT -> R.string.account_error_idempotency
    ai.argus.foundation.accounts.AccountProblem.VALIDATION -> R.string.account_error_validation
    ai.argus.foundation.accounts.AccountProblem.AMOUNT_INVALID -> R.string.account_error_amount
    ai.argus.foundation.accounts.AccountProblem.AMOUNT_PRECISION -> R.string.account_error_precision
    ai.argus.foundation.accounts.AccountProblem.AMOUNT_OUT_OF_RANGE -> R.string.account_error_range
    ai.argus.foundation.accounts.AccountProblem.CURRENCY_UNSUPPORTED -> R.string.account_error_currency
    ai.argus.foundation.accounts.AccountProblem.CURRENCY_LOCKED -> R.string.account_error_currency_locked
    ai.argus.foundation.accounts.AccountProblem.TYPE_LOCKED -> R.string.account_error_type_locked
    ai.argus.foundation.accounts.AccountProblem.NATURE_CHANGE_REQUIRES_EMPTY_ACCOUNT -> R.string.account_error_nature
    ai.argus.foundation.accounts.AccountProblem.DATE_INVALID -> R.string.account_error_date
    ai.argus.foundation.accounts.AccountProblem.DATE_IN_FUTURE -> R.string.account_error_future
    ai.argus.foundation.accounts.AccountProblem.TIME_ZONE_INVALID -> R.string.account_error_zone
    ai.argus.foundation.accounts.AccountProblem.NICKNAME_INVALID -> R.string.account_error_nickname
    ai.argus.foundation.accounts.AccountProblem.OWNERSHIP_SHARE_INVALID -> R.string.account_error_share
    ai.argus.foundation.accounts.AccountProblem.REASON_REQUIRED -> R.string.account_error_reason_required
    ai.argus.foundation.accounts.AccountProblem.REASON_INVALID -> R.string.account_error_reason
    ai.argus.foundation.accounts.AccountProblem.FIELD_MISSING -> R.string.account_error_missing
    ai.argus.foundation.accounts.AccountProblem.NETWORK -> R.string.account_error_network
    ai.argus.foundation.accounts.AccountProblem.SERVER -> R.string.account_error_server
    ai.argus.foundation.accounts.AccountProblem.INVALID_RESPONSE -> R.string.account_error_response
}
