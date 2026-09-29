package ai.argus.foundation.ui.accounts

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import ai.argus.foundation.R
import ai.argus.foundation.accounts.AccountsController
import ai.argus.foundation.accounts.DraftMode
import ai.argus.foundation.accounts.FinancialAccount
import ai.argus.foundation.accounts.formatAccountAmount
import ai.argus.foundation.auth.SessionStatus
import ai.argus.foundation.auth.SessionUiState
import kotlinx.coroutines.launch
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle
import java.util.Locale

/** Server records and drafts live with the session-scoped controller, never saved instance state. */
@Composable
internal fun AccountsPage(controller: AccountsController, session: SessionUiState?, onSignIn: () -> Unit) {
    val state by controller.state.collectAsState()
    val scope = rememberCoroutineScope()
    val focus = LocalFocusManager.current
    val locale = LocalConfiguration.current.locales[0].toLanguageTag()
    var manage by remember(state.ownershipEpoch) { mutableStateOf(false) }
    var discard by remember(state.ownershipEpoch) { mutableStateOf(false) }
    val verified = session?.status == SessionStatus.SIGNED_IN && session.profile != null
    LaunchedEffect(verified, session?.ownershipEpoch) { if (verified) controller.refresh() }
    val back: () -> Unit = {
        if (state.draft != null) discard = true
        else if (state.selected != null) controller.showList()
        else manage = false
    }
    BackHandler(enabled = verified && (state.draft != null || state.selected != null || manage)) { back() }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())
        .padding(horizontal = 24.dp, vertical = 16.dp).testTag("accounts_page"),
        verticalArrangement = Arrangement.spacedBy(16.dp)) {
        if (!verified || state.ownershipEpoch != session?.ownershipEpoch) {
            Text(stringResource(if (session?.status == SessionStatus.GUEST_PRESERVED)
                R.string.account_guest_required else R.string.account_sign_in_required))
            AccountAction(R.string.session_title, "accounts_sign_in", onClick = onSignIn)
            return@Column
        }
        if (state.draft != null || state.selected != null || manage) {
            TextButton(onClick = back, enabled = !state.busy, modifier = Modifier.testTag("account_back")) {
                Text(stringResource(R.string.back))
            }
        }
        Text(stringResource(R.string.account_server_notice), style = MaterialTheme.typography.bodySmall)
        if (state.busy) CircularProgressIndicator(Modifier.testTag("accounts_loading"))
        state.problem?.let { problem ->
            Text(stringResource(accountProblemLabel(problem)), Modifier.testTag("accounts_problem")
                .semantics { liveRegion = LiveRegionMode.Polite }, color = MaterialTheme.colorScheme.error)
        }
        val draft = state.draft
        when {
            draft != null -> {
                Text(stringResource(when (draft.mode) {
                    DraftMode.CREATE -> R.string.add_account
                    DraftMode.EDIT -> R.string.account_edit
                    DraftMode.OPENING -> if (draft.expectedRevision == null) R.string.account_add_opening else R.string.account_correct_opening
                    DraftMode.ARCHIVE -> if (draft.archived) R.string.account_archive else R.string.account_restore
                }), style = MaterialTheme.typography.titleLarge)
                if (state.reconciliationRequired) {
                    Text(stringResource(R.string.account_reconcile_notice), Modifier.testTag("account_reconciliation"))
                    if (state.canReconcile) state.selected?.let { AccountSummary(it, locale) }
                    AccountAction(R.string.account_read_current, "account_read_current", !state.busy) {
                        scope.launch { draft.accountId?.let { controller.open(it) } }
                    }
                    AccountAction(R.string.account_accept_current, "account_reconcile", !state.busy && state.canReconcile) {
                        scope.launch { controller.reconcileDraft() }
                    }
                }
                AccountForm(draft, !state.busy && !state.createRetryPending, state.problem, controller::updateDraft)
                if (state.createRetryPending) {
                    Text(stringResource(R.string.account_create_retry_notice))
                    AccountAction(R.string.account_retry_create, "account_retry_create", !state.busy) {
                        focus.clearFocus(); scope.launch { controller.retryCreate() }
                    }
                } else {
                    AccountAction(R.string.account_save, "account_save", !state.busy && !state.reconciliationRequired) {
                        focus.clearFocus(); scope.launch { controller.save() }
                    }
                }
                TextButton(onClick = { discard = true }, enabled = !state.busy,
                    modifier = Modifier.testTag("account_discard")) { Text(stringResource(R.string.account_discard)) }
            }
            state.selected != null -> {
                val account = requireNotNull(state.selected)
                AccountSummary(account, locale)
                AccountAction(R.string.account_edit, "account_edit", !state.busy) { controller.beginEdit(locale) }
                AccountAction(if (account.opening == null) R.string.account_add_opening else R.string.account_correct_opening,
                    "account_opening", !state.busy) { controller.beginOpening(locale) }
                AccountAction(if (account.archived) R.string.account_restore else R.string.account_archive,
                    "account_archive", !state.busy) { controller.beginArchive() }
                account.opening?.let { opening ->
                    Text(stringResource(R.string.account_history), style = MaterialTheme.typography.titleLarge)
                    opening.revisions.forEach { revision ->
                        Text(stringResource(R.string.account_revision, revision.revision))
                        Text("${account.currency} ${formatAccountAmount(revision.amount, locale)}")
                        Text(formatAccountDate(revision.asOf, revision.timeZone, locale))
                        revision.reason?.let { Text(it) }
                        HorizontalDivider()
                    }
                }
            }
            else -> {
                Text(stringResource(if (manage) R.string.account_manage else R.string.your_accounts),
                    style = MaterialTheme.typography.titleLarge)
                val accounts = state.accounts.filter { if (manage) it.archived else !it.archived }
                if (accounts.isEmpty() && state.loaded && !state.busy && state.problem == null) {
                    Text(stringResource(if (manage) R.string.account_no_archived else R.string.account_empty))
                }
                accounts.forEach { account ->
                    Column(Modifier.fillMaxWidth().clickable(enabled = !state.busy) {
                        scope.launch { controller.open(account.id) }
                    }.padding(vertical = 12.dp).testTag("account_row_${account.id}"),
                        verticalArrangement = Arrangement.spacedBy(8.dp)) { AccountSummary(account, locale, compact = true) }
                    HorizontalDivider()
                }
                AccountAction(R.string.add_account, "account_create", !state.busy) { controller.beginCreate(locale) }
                TextButton(onClick = { manage = !manage }, modifier = Modifier.testTag("account_manage")) {
                    Text(stringResource(if (manage) R.string.account_active else R.string.account_manage))
                }
                AccountAction(R.string.account_refresh, "accounts_refresh", !state.busy) {
                    scope.launch { controller.refresh() }
                }
            }
        }
    }
    if (discard && verified) AlertDialog(onDismissRequest = { discard = false },
        title = { Text(stringResource(R.string.account_discard)) },
        text = { Text(stringResource(R.string.account_discard_notice)) },
        confirmButton = { TextButton(onClick = { discard = false; controller.discardDraft() },
            modifier = Modifier.testTag("account_discard_confirm")) { Text(stringResource(R.string.account_discard)) } },
        dismissButton = { TextButton(onClick = { discard = false }) { Text(stringResource(R.string.account_keep_editing)) } })
}

@Composable
private fun AccountSummary(account: FinancialAccount, locale: String, compact: Boolean = false) {
    Text(account.nickname ?: stringResource(accountTypeLabels[account.type] ?: R.string.account_type_other_asset),
        style = MaterialTheme.typography.titleLarge, modifier = Modifier.testTag("account_name"))
    Text(stringResource(accountTypeLabels[account.type] ?: R.string.account_type_other_asset),
        style = MaterialTheme.typography.bodySmall)
    Text(if (account.balance.state == "unknown") stringResource(R.string.account_unknown)
        else "${account.currency} ${formatAccountAmount(requireNotNull(account.balance.amount), locale)}",
        Modifier.testTag("account_balance"), style = MaterialTheme.typography.titleLarge)
    if (!compact) {
        Text(stringResource(R.string.account_currency_value, account.currency))
        Text(stringResource(R.string.account_share_value, formatAccountAmount(java.math.BigDecimal(account.ownershipShareBps)
            .movePointLeft(2).stripTrailingZeros().toPlainString(), locale)))
        if (account.archived) Text(stringResource(R.string.account_archived))
        account.opening?.let { Text(formatAccountDate(it.asOf, it.timeZone, locale)) }
    }
}

private fun formatAccountDate(asOf: String, zone: String, locale: String): String = runCatching {
    OffsetDateTime.parse(asOf).atZoneSameInstant(ZoneId.of(zone))
        .format(DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM).withLocale(Locale.forLanguageTag(locale))) + " · " + zone
}.getOrDefault(asOf + " · " + zone)
