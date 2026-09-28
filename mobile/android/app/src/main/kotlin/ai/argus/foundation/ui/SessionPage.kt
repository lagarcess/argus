package ai.argus.foundation.ui

import android.content.res.Configuration
import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import ai.argus.foundation.R
import ai.argus.foundation.auth.SessionProblem
import ai.argus.foundation.auth.SessionStatus
import ai.argus.foundation.auth.SessionUiState
import java.util.Locale

/** The verified profile owns interface language; no parallel saved locale preference is created. */
@Composable
internal fun SessionLocale(state: SessionUiState?, content: @Composable () -> Unit) {
    val language = state?.takeIf { it.status == SessionStatus.SIGNED_IN }?.profile?.language
    val context = LocalContext.current
    val deviceConfiguration = LocalConfiguration.current
    val configuration = remember(deviceConfiguration, language) {
        Configuration(deviceConfiguration).apply {
            if (!language.isNullOrBlank()) setLocale(Locale.forLanguageTag(language))
        }
    }
    val localizedContext = remember(context, configuration) { context.createConfigurationContext(configuration) }
    CompositionLocalProvider(LocalConfiguration provides configuration, LocalContext provides localizedContext) {
        content()
    }
}

/** Auth state and verified identity belong to the session controller, never the form. */
@Composable
internal fun SessionPage(
    state: SessionUiState,
    onSignIn: (String, String) -> Unit,
    onSignOut: () -> Unit,
    onRetry: () -> Unit,
    onRecovery: (() -> Unit)?,
) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp, vertical = 16.dp).testTag("session_page"),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(stringResource(R.string.session_local_notice),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        state.problem?.let { problem ->
            Text(stringResource(problemMessage(problem)),
                Modifier.testTag("session_problem").semantics { liveRegion = LiveRegionMode.Polite },
                color = MaterialTheme.colorScheme.error)
        }
        when (state.status) {
            SessionStatus.DISABLED -> Text(stringResource(R.string.session_disabled))
            SessionStatus.SIGNED_OUT -> SignInForm(onSignIn, onRecovery)
            SessionStatus.WORKING -> {
                CircularProgressIndicator()
                Text(stringResource(R.string.session_working),
                    Modifier.testTag("session_working").semantics { liveRegion = LiveRegionMode.Polite })
            }
            SessionStatus.SIGNED_IN -> {
                // A signed-in status without a verified profile must not fabricate an identity.
                state.profile?.let { profile ->
                    Text(stringResource(R.string.session_verified),
                        Modifier.testTag("session_verified"), style = MaterialTheme.typography.titleLarge)
                    profile.displayName?.let { Text(it, Modifier.testTag("session_display_name")) }
                    profile.email?.let { Text(it, Modifier.testTag("session_email")) }
                    Text(stringResource(R.string.session_profile_basis), style = MaterialTheme.typography.bodySmall)
                }
                Text(stringResource(R.string.session_financial_boundary))
                SessionButton(R.string.session_sign_out, "session_sign_out", onSignOut)
                SessionButton(R.string.session_switch, "session_switch", onSignOut)
                Text(stringResource(R.string.session_switch_notice), style = MaterialTheme.typography.bodySmall)
            }
            SessionStatus.GUEST_PRESERVED -> {
                Text(stringResource(R.string.session_guest_title), style = MaterialTheme.typography.titleLarge)
                Text(stringResource(R.string.session_guest_boundary), Modifier.testTag("session_guest_boundary"))
            }
            SessionStatus.RECOVERY_REQUIRED -> {
                Text(stringResource(R.string.session_verification_pending),
                    Modifier.testTag("session_verification_pending"))
                SessionButton(R.string.session_retry, "session_retry", onRetry)
                SessionButton(R.string.session_sign_out, "session_sign_out", onSignOut)
            }
            SessionStatus.REVOCATION_FAILED -> {
                Text(stringResource(R.string.session_revocation_pending),
                    Modifier.testTag("session_revocation_pending"))
                SessionButton(R.string.session_retry_sign_out, "session_retry_sign_out", onSignOut)
            }
        }
    }
}

@Composable
private fun SignInForm(onSignIn: (String, String) -> Unit, onRecovery: (() -> Unit)?) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    val focus = LocalFocusManager.current
    DisposableEffect(Unit) { onDispose { password = "" } }
    val canSubmit = email.isNotBlank() && password.isNotEmpty()
    val submit = {
        if (canSubmit) {
            val submittedPassword = password
            password = ""
            focus.clearFocus()
            onSignIn(email.trim(), submittedPassword)
        }
    }
    Text(stringResource(R.string.session_sign_in), style = MaterialTheme.typography.titleLarge)
    Text(stringResource(R.string.session_optional))
    OutlinedTextField(
        value = email, onValueChange = { email = it },
        modifier = Modifier.fillMaxWidth().testTag("session_email_input"),
        label = { Text(stringResource(R.string.session_email_label)) }, singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next),
    )
    OutlinedTextField(
        value = password, onValueChange = { password = it },
        modifier = Modifier.fillMaxWidth().testTag("session_password_input"),
        label = { Text(stringResource(R.string.session_password_label)) }, singleLine = true,
        visualTransformation = PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done,
            autoCorrectEnabled = false),
        keyboardActions = KeyboardActions(onDone = { submit() }),
    )
    Button(onClick = submit, enabled = canSubmit,
        modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("session_submit")) {
        Text(stringResource(R.string.session_sign_in))
    }
    if (onRecovery != null) {
        TextButton(onClick = { password = ""; focus.clearFocus(); onRecovery() },
            modifier = Modifier.heightIn(min = 48.dp).testTag("session_recovery")) {
            Text(stringResource(R.string.session_forgot_password))
        }
        Text(stringResource(R.string.session_browser_recovery), style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun SessionButton(@StringRes label: Int, tag: String, onClick: () -> Unit) {
    OutlinedButton(onClick = onClick,
        modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag(tag)) {
        Text(stringResource(label))
    }
}

private fun problemMessage(problem: SessionProblem): Int = when (problem) {
    SessionProblem.INVALID_CREDENTIALS -> R.string.session_error_credentials
    SessionProblem.REJECTED_SESSION -> R.string.session_error_rejected
    SessionProblem.NETWORK -> R.string.session_error_network
    SessionProblem.VERIFICATION_UNAVAILABLE -> R.string.session_error_verification
    SessionProblem.INVALID_RESPONSE -> R.string.session_error_response
    SessionProblem.STORAGE -> R.string.session_error_storage
    SessionProblem.REVOCATION -> R.string.session_error_revocation
    SessionProblem.UNSUPPORTED_GUEST -> R.string.session_error_guest
}
