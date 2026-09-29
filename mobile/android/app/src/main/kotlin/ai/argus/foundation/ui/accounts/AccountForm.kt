package ai.argus.foundation.ui.accounts

import android.app.DatePickerDialog
import android.app.TimePickerDialog
import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import ai.argus.foundation.R
import ai.argus.foundation.accounts.AccountDraft
import ai.argus.foundation.accounts.AccountProblem
import ai.argus.foundation.accounts.formatAccountAmount
import ai.argus.foundation.accounts.parseAccountAmount
import ai.argus.foundation.accounts.DraftMode
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle
import java.util.Locale

@Composable
internal fun AccountForm(draft: AccountDraft, enabled: Boolean, problem: AccountProblem?, onChange: (AccountDraft) -> Unit) {
    fun error(vararg problems: AccountProblem): Int? = problem?.takeIf { it in problems }?.let(::accountProblemLabel)
    if (draft.mode == DraftMode.CREATE || draft.mode == DraftMode.EDIT) {
        AccountField(draft.nickname, R.string.account_nickname, "account_nickname", enabled, error = error(AccountProblem.NICKNAME_INVALID)) {
            onChange(draft.copy(nickname = it))
        }
        var expanded by remember { mutableStateOf(false) }
        Text(stringResource(R.string.account_type_label), style = MaterialTheme.typography.labelLarge)
        Column {
            OutlinedButton(onClick = { expanded = true }, enabled = enabled,
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("account_type")) {
                Text(stringResource(accountTypeLabels[draft.type] ?: R.string.account_type_other_asset))
            }
            DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                accountTypeLabels.forEach { (type, label) ->
                    DropdownMenuItem(text = { Text(stringResource(label)) },
                        modifier = Modifier.testTag("account_type_$type"), onClick = {
                            expanded = false
                            onChange(draft.copy(type = type, ownershipPercent =
                                if (draft.mode == DraftMode.CREATE && type !in setOf("property", "vehicle", "other_asset"))
                                    "100" else draft.ownershipPercent))
                        })
                }
            }
        }
        error(AccountProblem.TYPE_LOCKED, AccountProblem.NATURE_CHANGE_REQUIRES_EMPTY_ACCOUNT)?.let { InlineError(it) }
        AccountField(draft.currency, R.string.account_currency, "account_currency", enabled, error = error(AccountProblem.CURRENCY_UNSUPPORTED, AccountProblem.CURRENCY_LOCKED)) {
            onChange(draft.copy(currency = it))
        }
        Text(stringResource(R.string.account_currency_hint), style = MaterialTheme.typography.bodySmall)
        if (draft.mode == DraftMode.EDIT) {
            AccountField(draft.ownershipPercent, R.string.account_share, "account_share", enabled,
                KeyboardType.Decimal, error = error(AccountProblem.OWNERSHIP_SHARE_INVALID)) { onChange(draft.copy(ownershipPercent = it)) }
            Text(stringResource(R.string.account_share_hint), style = MaterialTheme.typography.bodySmall)
        } else if (draft.type in setOf("property", "vehicle", "other_asset")) {
            CreateOwnership(draft, enabled, error(AccountProblem.OWNERSHIP_SHARE_INVALID), onChange)
        }
    }
    if (draft.mode == DraftMode.CREATE) {
        androidx.compose.foundation.layout.Row {
            Checkbox(checked = draft.balanceKnown, enabled = enabled,
                onCheckedChange = { onChange(draft.copy(balanceKnown = it)) },
                modifier = Modifier.testTag("account_known"))
            Text(stringResource(R.string.account_known), Modifier.padding(top = 12.dp))
        }
        if (!draft.balanceKnown) Text(stringResource(R.string.account_unknown_hint))
    }
    if (draft.mode == DraftMode.OPENING || (draft.mode == DraftMode.CREATE && draft.balanceKnown)) {
        Text(stringResource(R.string.account_entering_currency, draft.currency))
        Text(stringResource(accountTypeLabels[draft.type] ?: R.string.account_type_other_asset))
        Text(stringResource(R.string.account_positive_owed), style = MaterialTheme.typography.bodySmall)
        AccountField(draft.amount, when (draft.type) {
            "credit_card", "other_debt" -> R.string.account_amount_owed
            "property", "vehicle", "other_asset" -> R.string.account_estimated_value
            else -> R.string.account_amount
        }, "account_amount", enabled, KeyboardType.Decimal,
            error = error(AccountProblem.AMOUNT_INVALID, AccountProblem.AMOUNT_PRECISION, AccountProblem.AMOUNT_OUT_OF_RANGE),
            onBlur = { parseAccountAmount(draft.amount, draft.localeTag)?.let {
                onChange(draft.copy(amount = formatAccountAmount(it, draft.localeTag)))
            } }) {
            onChange(draft.copy(amount = it))
        }
        Text(stringResource(R.string.account_amount_example, formatAccountAmount("1234.56", draft.localeTag)),
            style = MaterialTheme.typography.bodySmall)
        if (draft.mode == DraftMode.OPENING) {
            BalanceDate(draft, enabled, onChange)
            error(AccountProblem.DATE_INVALID, AccountProblem.DATE_IN_FUTURE)?.let { InlineError(it) }
            AccountField(draft.timeZone, R.string.account_time_zone, "account_time_zone", enabled,
                error = error(AccountProblem.TIME_ZONE_INVALID)) { onChange(draft.copy(timeZone = it)) }
            Text(stringResource(R.string.account_zone_hint), style = MaterialTheme.typography.bodySmall)
            AccountField(draft.reason, if (draft.expectedRevision != null) R.string.account_reason_required
                else R.string.account_reason_optional, "account_reason", enabled,
                error = error(AccountProblem.REASON_REQUIRED, AccountProblem.REASON_INVALID, AccountProblem.FIELD_MISSING)) {
                onChange(draft.copy(reason = it))
            }
        }
    }
    if (draft.mode == DraftMode.ARCHIVE) {
        Text(stringResource(if (draft.archived) R.string.account_archive_explanation else R.string.account_restore_explanation))
    }
}

@Composable
private fun BalanceDate(draft: AccountDraft, enabled: Boolean, onChange: (AccountDraft) -> Unit) {
    val context = LocalContext.current
    val parsed = runCatching { OffsetDateTime.parse(draft.asOf).atZoneSameInstant(ZoneId.of(draft.timeZone)) }.getOrNull()
    val locale = Locale.forLanguageTag(draft.localeTag)
    Text(stringResource(R.string.account_as_of), style = MaterialTheme.typography.labelLarge)
    Text(parsed?.format(DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM).withLocale(locale)) ?: draft.asOf,
        Modifier.testTag("account_date_value"))
    OutlinedButton(enabled = enabled && parsed != null, modifier = Modifier.fillMaxWidth().testTag("account_date"),
        onClick = {
            parsed?.let { date ->
                DatePickerDialog(context, { _, year, month, day ->
                    val updated = java.time.LocalDate.of(year, month + 1, day).atTime(date.toLocalTime()).atZone(date.zone)
                    onChange(draft.copy(asOf = updated.toOffsetDateTime().toString()))
                }, date.year, date.monthValue - 1, date.dayOfMonth).show()
            }
        }) { Text(stringResource(R.string.account_change_date)) }
    OutlinedButton(enabled = enabled && parsed != null, modifier = Modifier.fillMaxWidth().testTag("account_time"),
        onClick = {
            parsed?.let { date ->
                TimePickerDialog(context, { _, hour, minute ->
                    onChange(draft.copy(asOf = date.withHour(hour).withMinute(minute).withSecond(0)
                        .withNano(0).toOffsetDateTime().toString()))
                }, date.hour, date.minute, true).show()
            }
        }) { Text(stringResource(R.string.account_change_time)) }
}

@Composable
internal fun AccountField(value: String, @StringRes label: Int, tag: String, enabled: Boolean,
    keyboard: KeyboardType = KeyboardType.Text, @StringRes error: Int? = null,
    onBlur: (() -> Unit)? = null, onChange: (String) -> Unit) {
    var wasFocused by remember { mutableStateOf(false) }
    OutlinedTextField(value, onChange, enabled = enabled,
        modifier = Modifier.fillMaxWidth().testTag(tag).onFocusChanged { focus ->
            if (wasFocused && !focus.isFocused) onBlur?.invoke()
            wasFocused = focus.isFocused
        }, isError = error != null, supportingText = { error?.let { InlineError(it) } }, label = { Text(stringResource(label)) },
        singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = keyboard,
            imeAction = ImeAction.Next, autoCorrectEnabled = false))
}

@Composable
internal fun AccountAction(@StringRes label: Int, tag: String, enabled: Boolean = true, onClick: () -> Unit) {
    Button(onClick, enabled = enabled, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag(tag)) {
        Text(stringResource(label))
    }
}

@Composable
private fun InlineError(@StringRes message: Int) {
    Text(stringResource(message), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
}
