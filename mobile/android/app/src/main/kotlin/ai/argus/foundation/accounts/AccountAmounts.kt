package ai.argus.foundation.accounts

import java.math.BigDecimal
import java.text.DecimalFormatSymbols
import java.util.Locale

/** Consume the whole locale input. Grouped paste must have complete three-digit groups. */
fun parseAccountAmount(input: String, localeTag: String): String? {
    val value = input.trim()
    if (value.length > 100) return null
    val symbols = DecimalFormatSymbols.getInstance(Locale.forLanguageTag(localeTag))
    val negative = value.startsWith('-')
    val unsigned = if (negative) value.drop(1) else value
    val parts = unsigned.split(symbols.decimalSeparator)
    if (parts.size !in 1..2) return null
    val integer = parts[0]
    val groups = integer.split(symbols.groupingSeparator)
    fun digits(part: String) = part.isNotEmpty() && part.all { it in '0'..'9' }
    if (groups.size == 1) {
        if (!digits(integer)) return null
    } else if (groups.first().length !in 1..3 || groups.any { !digits(it) } || groups.drop(1).any { it.length != 3 }) {
        return null
    }
    if (parts.size == 2 && !digits(parts[1])) return null
    val canonical = (if (negative) "-" else "") + groups.joinToString("") +
        (if (parts.size == 2) ".${parts[1]}" else "")
    return canonical.takeIf { it.length <= 40 }
}

/** Preserve every digit and response scale. No floating point or currency rounding. */
fun formatAccountAmount(amount: String, localeTag: String): String {
    val symbols = DecimalFormatSymbols.getInstance(Locale.forLanguageTag(localeTag))
    val negative = amount.startsWith('-')
    val parts = (if (negative) amount.drop(1) else amount).split('.')
    val grouped = parts[0].reversed().chunked(3).joinToString(symbols.groupingSeparator.toString()).reversed()
    return (if (negative) "-" else "") + grouped +
        (if (parts.size == 2) "${symbols.decimalSeparator}${parts[1]}" else "")
}

internal fun openingInput(account: FinancialAccount, localeTag: String): String {
    val amount = account.opening?.amount ?: return ""
    val input = if (account.nature == "liability") BigDecimal(amount).negate().toPlainString() else amount
    return formatAccountAmount(input, localeTag)
}
