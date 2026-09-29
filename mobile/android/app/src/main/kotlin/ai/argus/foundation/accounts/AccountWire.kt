package ai.argus.foundation.accounts

import kotlinx.serialization.json.*

internal val accountsJson = Json { ignoreUnknownKeys = true }

internal fun decodeAccount(value: JsonObject): FinancialAccount = with(value) {
    FinancialAccount(
        text("id"), text("type"), text("nature"), text("currency"), number("currency_fraction_digits"),
        optionalText("nickname"), getValue("archived").jsonPrimitive.boolean, number("ownership_share_bps"),
        number("version"), text("created_at"), text("updated_at"),
        getValue("balance").jsonObject.let { balance -> AccountBalance(
            balance.text("state"), balance.optionalLong("amount_minor"), balance.optionalText("amount"),
            balance.optionalText("as_of"), balance.optionalText("basis"), balance.long("activity_since_tracking_minor"),
        ) },
        get("opening")?.takeUnless { it == JsonNull }?.jsonObject?.let { opening -> AccountOpening(
            opening.text("record_id"), opening.number("revision"), opening.long("amount_minor"),
            opening.text("amount"), opening.text("as_of"), opening.text("time_zone"), opening.optionalText("reason"),
            opening.text("recorded_at"), opening.getValue("revisions").jsonArray.map { entry ->
                val revision = entry.jsonObject
                OpeningRevision(revision.number("revision"), revision.long("amount_minor"), revision.text("amount"),
                    revision.text("as_of"), revision.text("time_zone"), revision.optionalText("reason"),
                    revision.optionalText("recorded_by"), revision.text("recorded_at"))
            },
        ) },
    )
}

private fun JsonObject.text(key: String): String = getValue(key).jsonPrimitive.let {
    require(it.isString)
    it.content
}
private fun JsonObject.optionalText(key: String): String? = get(key)?.takeUnless { it == JsonNull }?.let { text(key) }
private fun JsonObject.number(key: String): Int = getValue(key).jsonPrimitive.int
private fun JsonObject.long(key: String): Long = getValue(key).jsonPrimitive.long
private fun JsonObject.optionalLong(key: String): Long? = get(key)?.takeUnless { it == JsonNull }?.jsonPrimitive?.long

internal fun accountProblem(code: String?): AccountProblem = when (code) {
    "financial_accounts_unavailable" -> AccountProblem.UNAVAILABLE
    "account_conversion_required" -> AccountProblem.REGISTRATION_REQUIRED
    "financial_account_not_found" -> AccountProblem.NOT_FOUND
    "unauthorized" -> AccountProblem.AUTH_REQUIRED
    "stale_version" -> AccountProblem.STALE_VERSION
    "idempotency_conflict" -> AccountProblem.IDEMPOTENCY_CONFLICT
    "amount_invalid" -> AccountProblem.AMOUNT_INVALID
    "amount_precision" -> AccountProblem.AMOUNT_PRECISION
    "amount_out_of_range" -> AccountProblem.AMOUNT_OUT_OF_RANGE
    "currency_unsupported" -> AccountProblem.CURRENCY_UNSUPPORTED
    "currency_locked" -> AccountProblem.CURRENCY_LOCKED
    "type_locked" -> AccountProblem.TYPE_LOCKED
    "nature_change_requires_empty_account" -> AccountProblem.NATURE_CHANGE_REQUIRES_EMPTY_ACCOUNT
    "date_invalid" -> AccountProblem.DATE_INVALID
    "date_in_future" -> AccountProblem.DATE_IN_FUTURE
    "time_zone_invalid" -> AccountProblem.TIME_ZONE_INVALID
    "nickname_invalid" -> AccountProblem.NICKNAME_INVALID
    "ownership_share_invalid" -> AccountProblem.OWNERSHIP_SHARE_INVALID
    "reason_required" -> AccountProblem.REASON_REQUIRED
    "reason_invalid" -> AccountProblem.REASON_INVALID
    "field_missing" -> AccountProblem.FIELD_MISSING
    "validation_error", "idempotency_key_required", "account_type_unsupported" -> AccountProblem.VALIDATION
    else -> AccountProblem.SERVER
}
