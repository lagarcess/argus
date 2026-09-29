package ai.argus.foundation.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import ai.argus.foundation.Appearance
import ai.argus.foundation.R
import ai.argus.foundation.auth.SessionStatus
import ai.argus.foundation.auth.SessionUiState

@Composable
internal fun SettingsPage(
    onPreferences: () -> Unit,
    unavailable: () -> Unit,
    sessionState: SessionUiState? = null,
    onSession: () -> Unit = {},
) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp)) {
        if (sessionState == null) {
            DetailRow(R.string.guest_identity, R.string.guest_identity_detail)
        } else {
            val identity = when (sessionState.status) {
                SessionStatus.SIGNED_IN -> R.string.session_registered_identity
                SessionStatus.GUEST_PRESERVED -> R.string.session_guest_title
                else -> R.string.session_title
            }
            DetailRow(identity, R.string.session_settings_detail, onClick = onSession,
                modifier = Modifier.testTag("session_entry"))
        }
        SectionTitle(R.string.app_group)
        DetailRow(R.string.preferences, R.string.preferences_detail, onClick = onPreferences,
            modifier = Modifier.testTag("preferences"))
        DetailRow(R.string.personalization, R.string.personalization_detail, onClick = unavailable)
        DetailRow(R.string.notifications, R.string.notifications_detail, onClick = unavailable)
        SectionTitle(R.string.account_group)
        DetailRow(R.string.security, R.string.security_detail, onClick = unavailable)
        DetailRow(R.string.data_privacy, R.string.data_privacy_detail, onClick = unavailable)
        DetailRow(R.string.usage, R.string.usage_detail, onClick = unavailable)
        SectionTitle(R.string.support_group)
        DetailRow(R.string.help_feedback, R.string.help_feedback_detail, onClick = unavailable)
        Text(stringResource(if (sessionState == null) R.string.settings_footer
            else R.string.session_settings_footer), Modifier.padding(vertical = 24.dp),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
internal fun PreferencesPage(appearance: Appearance, onAppearanceChange: (Appearance) -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp)) {
        SectionTitle(R.string.appearance)
        Column(Modifier.selectableGroup()) {
            Appearance.entries.forEach { option ->
                val label = when (option) {
                    Appearance.LIGHT -> R.string.appearance_light
                    Appearance.DARK -> R.string.appearance_dark
                    Appearance.SYSTEM -> R.string.appearance_system
                }
                Row(
                    Modifier.fillMaxWidth().heightIn(min = 56.dp)
                        .selectable(selected = option == appearance, role = Role.RadioButton,
                            onClick = { onAppearanceChange(option) })
                        .testTag("appearance_${option.name}").padding(vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    RadioButton(selected = option == appearance, onClick = null)
                    Text(stringResource(label), style = MaterialTheme.typography.bodyLarge)
                }
            }
        }
        HorizontalDivider()
        Text(stringResource(R.string.appearance_notice), Modifier.padding(vertical = 16.dp),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        SectionTitle(R.string.language_region)
        Text(stringResource(if (LocalSessionEnabled.current) R.string.session_language_notice
            else R.string.language_notice), style = MaterialTheme.typography.bodyLarge)
        SampleNotice()
    }
}
