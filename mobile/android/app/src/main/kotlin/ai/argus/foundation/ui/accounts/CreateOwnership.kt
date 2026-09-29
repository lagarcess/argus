package ai.argus.foundation.ui.accounts

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import ai.argus.foundation.R
import ai.argus.foundation.accounts.AccountDraft

/** Optional asset share is disclosed only after the person chooses Change. */
@Composable
internal fun CreateOwnership(draft: AccountDraft, enabled: Boolean, @StringRes error: Int?,
    onChange: (AccountDraft) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    var another by remember { mutableStateOf(false) }
    Text(if (draft.ownershipPercent == "100") stringResource(R.string.account_own_all)
        else stringResource(R.string.account_share_value, draft.ownershipPercent))
    error?.let { Text(stringResource(it), color = MaterialTheme.colorScheme.error) }
    TextButton(enabled = enabled, onClick = { expanded = true }, modifier = Modifier.testTag("account_share_change")) {
        Text(stringResource(R.string.account_change))
    }
    if (expanded) AlertDialog(onDismissRequest = { expanded = false },
        title = { Text(stringResource(R.string.account_share)) },
        text = { Column {
            TextButton(onClick = { onChange(draft.copy(ownershipPercent = "100")); another = false; expanded = false },
                modifier = Modifier.testTag("account_share_all")) { Text(stringResource(R.string.account_share_all)) }
            TextButton(onClick = { onChange(draft.copy(ownershipPercent = "50")); another = false; expanded = false },
                modifier = Modifier.testTag("account_share_half")) { Text(stringResource(R.string.account_share_half)) }
            TextButton(onClick = { another = true }, modifier = Modifier.testTag("account_share_other")) {
                Text(stringResource(R.string.account_share_other))
            }
            if (another) AccountField(draft.ownershipPercent, R.string.account_share, "account_share", enabled,
                KeyboardType.Decimal, error = error) { onChange(draft.copy(ownershipPercent = it)) }
        } },
        confirmButton = { TextButton(onClick = { expanded = false }) { Text(stringResource(R.string.got_it)) } })
}
