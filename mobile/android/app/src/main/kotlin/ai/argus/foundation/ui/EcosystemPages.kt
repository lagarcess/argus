package ai.argus.foundation.ui

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import ai.argus.foundation.R

@Composable
internal fun EcosystemPage(
    destination: Destination, requireRegistration: () -> Unit, unavailable: () -> Unit,
) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp)) {
        SampleNotice()
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = unavailable, modifier = Modifier.heightIn(min = 48.dp),
                contentPadding = PaddingValues(horizontal = 0.dp)) {
                Text(stringResource(R.string.personal_space),
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            QuietIcon(ArgusIcons.Add, R.string.add_space, unavailable)
        }
        when (destination) {
            Destination.HOME -> HomeSample(requireRegistration)
            Destination.ACCOUNTS -> AccountsSample(requireRegistration)
            Destination.PLAN -> PlanSample(requireRegistration)
            Destination.SEARCH -> SearchSample(requireRegistration)
            Destination.ARGUS -> Unit
        }
        Text(stringResource(R.string.ecosystem_guest_notice), Modifier.padding(vertical = 24.dp),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun HomeSample(requireRegistration: () -> Unit) {
    SectionTitle(R.string.recorded_position)
    Text(stringResource(R.string.dop_balance), style = MaterialTheme.typography.headlineLarge)
    Text(stringResource(R.string.balance_basis), Modifier.padding(vertical = 12.dp),
        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    DetailRow(R.string.cash_bank, R.string.dop_cash_bank)
    DetailRow(R.string.you_owe, R.string.dop_debt)
    DetailRow(R.string.record_activity, R.string.record_activity_detail, onClick = requireRegistration,
        modifier = Modifier.testTag("guest_action_direct"))
    SectionTitle(R.string.coming_up)
    DetailRow(R.string.sample_rent, R.string.sample_rent_detail)
    DetailRow(R.string.currency_note, R.string.usd_separate)
}

@Composable
private fun AccountsSample(requireRegistration: () -> Unit) {
    SectionTitle(R.string.your_accounts)
    DetailRow(R.string.cash, R.string.sample_cash, onClick = requireRegistration)
    DetailRow(R.string.bank, R.string.sample_bank, onClick = requireRegistration)
    DetailRow(R.string.dollar_savings, R.string.sample_dollars, onClick = requireRegistration)
    DetailRow(R.string.credit_card, R.string.sample_card, onClick = requireRegistration)
    DetailRow(R.string.add_account, R.string.add_account_detail, onClick = requireRegistration,
        modifier = Modifier.testTag("guest_action_direct"))
    Text(stringResource(R.string.accounts_currency_notice), Modifier.padding(vertical = 20.dp),
        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
private fun PlanSample(requireRegistration: () -> Unit) {
    SectionTitle(R.string.plan_overview)
    Text(stringResource(R.string.plan_intro), style = MaterialTheme.typography.bodyMedium)
    SectionTitle(R.string.goals)
    DetailRow(R.string.emergency_fund, R.string.sample_goal, onClick = requireRegistration)
    SectionTitle(R.string.budgets)
    DetailRow(R.string.groceries, R.string.sample_budget, onClick = requireRegistration)
    SectionTitle(R.string.debts)
    DetailRow(R.string.credit_card, R.string.sample_debt, onClick = requireRegistration)
    DetailRow(R.string.add_plan, R.string.add_plan_detail, onClick = requireRegistration,
        modifier = Modifier.testTag("guest_action_direct"))
}

@Composable
private fun SearchSample(requireRegistration: () -> Unit) {
    SectionTitle(R.string.find_again)
    Text(stringResource(R.string.search_intro), style = MaterialTheme.typography.bodyMedium)
    DetailRow(R.string.search_records, R.string.search_records_detail, onClick = requireRegistration,
        modifier = Modifier.testTag("guest_action_direct"))
    SectionTitle(R.string.sample_results)
    DetailRow(R.string.emergency_fund, R.string.search_goal, onClick = requireRegistration)
    DetailRow(R.string.sample_rent, R.string.search_record, onClick = requireRegistration)
    DetailRow(R.string.sample_chat_title, R.string.search_chat, onClick = requireRegistration)
}

@Composable
internal fun SecondarySamplePage(@StringRes title: Int, @StringRes body: Int) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp)) {
        SampleNotice()
        SectionTitle(title)
        Text(stringResource(body), style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
internal fun RecentsPage(onSettings: () -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp)) {
        SampleNotice()
        SectionTitle(R.string.recents_empty)
        Text(stringResource(R.string.recents_body), style = MaterialTheme.typography.bodyLarge)
        DetailRow(R.string.profile_settings, R.string.preferences_detail, onClick = onSettings,
            modifier = Modifier.testTag("settings"))
    }
}
