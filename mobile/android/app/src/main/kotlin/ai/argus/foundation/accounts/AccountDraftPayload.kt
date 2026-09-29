package ai.argus.foundation.accounts

import java.math.BigDecimal
import kotlinx.serialization.json.*

internal fun draftPayload(draft: AccountDraft, original: AccountDraft): JsonObject = buildJsonObject {
    when (draft.mode) {
        DraftMode.CREATE -> {
            put("type", draft.type)
            put("currency", draft.currency.trim().uppercase(java.util.Locale.ROOT))
            put("nickname", draft.nickname)
            if (draft.ownershipPercent != "100") put("ownership_share_bps", ownershipBps(draft))
            if (draft.balanceKnown) {
                put("amount", amount(draft))
                optionalDate(draft)
            }
        }
        DraftMode.EDIT -> {
            put("expected_version", requireNotNull(draft.expectedVersion))
            if (draft.nickname != original.nickname) put("nickname", draft.nickname)
            if (draft.type != original.type) put("type", draft.type)
            if (draft.currency != original.currency) put("currency", draft.currency.trim().uppercase(java.util.Locale.ROOT))
            if (draft.ownershipPercent != original.ownershipPercent) put("ownership_share_bps", ownershipBps(draft))
        }
        DraftMode.ARCHIVE -> {
            put("expected_version", requireNotNull(draft.expectedVersion))
            put("archived", draft.archived)
        }
        DraftMode.OPENING -> {
            put("expected_version", requireNotNull(draft.expectedVersion))
            put("expected_revision", draft.expectedRevision?.let(::JsonPrimitive) ?: JsonNull)
            if (draft.expectedRevision == null || parseAccountAmount(draft.amount, draft.localeTag) != parseAccountAmount(original.amount, original.localeTag)) put("amount", amount(draft))
            if (draft.expectedRevision == null || draft.asOf != original.asOf) {
                if (draft.asOf.isNotBlank()) put("as_of", draft.asOf)
            }
            if (draft.expectedRevision == null || draft.timeZone != original.timeZone) {
                if (draft.timeZone.isNotBlank()) put("time_zone", draft.timeZone)
            }
            put("reason", draft.reason)
        }
    }
}

private fun JsonObjectBuilder.optionalDate(draft: AccountDraft) {
    if (draft.asOf.isNotBlank()) put("as_of", draft.asOf)
    if (draft.timeZone.isNotBlank()) put("time_zone", draft.timeZone)
}
private fun amount(draft: AccountDraft): String = parseAccountAmount(draft.amount, draft.localeTag)
    ?: throw AccountFailure(AccountProblem.AMOUNT_INVALID)
private fun ownershipBps(draft: AccountDraft): Int {
    val value = parseAccountAmount(draft.ownershipPercent, draft.localeTag)
        ?: throw AccountFailure(AccountProblem.OWNERSHIP_SHARE_INVALID)
    return try { BigDecimal(value).movePointRight(2).intValueExact() }
    catch (_: ArithmeticException) { throw AccountFailure(AccountProblem.OWNERSHIP_SHARE_INVALID) }
}
