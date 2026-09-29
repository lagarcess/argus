package ai.argus.foundation.accounts

import org.junit.Assert.*
import org.junit.Test

class AccountAmountsTest {
    @Test fun exactGroupedAmountsRoundTripBeyondFloatingPointRange() {
        listOf("en", "es-419", "es-ES").forEach { locale ->
            listOf("9007199254740.99", "92233720368547758.07", "-100.00", "0.000", "12345678901234567890").forEach { decimal ->
                assertEquals(decimal, parseAccountAmount(formatAccountAmount(decimal, locale), locale))
            }
        }
        assertEquals("9,007,199,254,740.99", formatAccountAmount("9007199254740.99", "en"))
        assertEquals("1.234,50", formatAccountAmount("1234.50", "es-ES"))
    }
    @Test fun consumesCompleteInputAndRejectsMalformedGrouping() {
        listOf("1,23.00", "12,3456", "1e3", "12 dollars", "NaN", "+10", "--10", ".5", "1.", "1,", "1.2.3", "1 000").forEach {
            assertNull(it, parseAccountAmount(it, "en"))
        }
        assertEquals("1234.50", parseAccountAmount("1,234.50", "en"))
        assertEquals("1234.50", parseAccountAmount("1.234,50", "es-ES"))
    }
    @Test fun debtOpeningPrefillUsesOwedConventionIncludingCreditBalance() {
        val account = fixtureAccount(owed = true)
        assertEquals("100.00", openingInput(account, "en"))
        assertEquals("-100.00", openingInput(account.copy(opening = account.opening!!.copy(amount = "100.00")), "en"))
    }
    @Test fun dateOnlyCorrectionOmitsAmountAndUnchangedZoneAndCapturesBothVersions() {
        val original = AccountDraft(mode = DraftMode.OPENING, expectedVersion = 7, expectedRevision = 3,
            amount = "100.00", asOf = "2026-09-28T09:15:00-04:00", timeZone = "America/Santo_Domingo")
        val body = draftPayload(original.copy(asOf = "2026-09-27T09:15:00-04:00", reason = "Date correction"), original)
        assertEquals("7", body["expected_version"].toString())
        assertEquals("3", body["expected_revision"].toString())
        assertFalse(body.containsKey("amount"))
        assertFalse(body.containsKey("time_zone"))
    }
    @Test fun zeroAndUnknownAreDifferentAndPercentRemainsExact() {
        val original = AccountDraft(amount = "0", ownershipPercent = "25.25")
        val known = draftPayload(original, original)
        val unknown = draftPayload(original.copy(balanceKnown = false), original)
        assertEquals("\"0\"", known["amount"].toString())
        assertEquals("2525", known["ownership_share_bps"].toString())
        assertFalse(unknown.containsKey("amount"))
        assertFalse(unknown.containsKey("as_of"))
    }
    @Test fun clearingNicknameSendsAnExplicitValue() {
        val original = AccountDraft(mode = DraftMode.EDIT, expectedVersion = 2, nickname = "Old name")
        assertEquals("\"\"", draftPayload(original.copy(nickname = ""), original)["nickname"].toString())
    }
}
