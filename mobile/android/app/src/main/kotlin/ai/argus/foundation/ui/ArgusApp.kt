package ai.argus.foundation.ui

import androidx.activity.compose.BackHandler
import androidx.annotation.StringRes
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.nestedscroll.NestedScrollSource
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import ai.argus.foundation.Appearance
import ai.argus.foundation.R
import ai.argus.foundation.auth.SessionStatus
import ai.argus.foundation.auth.SessionUiState

internal enum class Destination(@StringRes val title: Int) {
    HOME(R.string.home), ACCOUNTS(R.string.accounts), ARGUS(R.string.argus),
    PLAN(R.string.plan), SEARCH(R.string.search),
}

internal enum class Page(@StringRes val title: Int) {
    ROOT(R.string.argus), SETTINGS(R.string.profile_settings),
    PREFERENCES(R.string.preferences), UPDATES(R.string.updates), RECENTS(R.string.recents),
    SESSION(R.string.session_title),
}

/** Financial pages remain samples; optional session access is isolated in Settings. */
@Composable
fun ArgusApp(
    appearance: Appearance,
    onAppearanceChange: (Appearance) -> Unit,
    sessionState: SessionUiState? = null,
    onSignIn: (String, String) -> Unit = { _, _ -> },
    onSignOut: () -> Unit = {},
    onSessionRetry: () -> Unit = {},
    onRecovery: (() -> Unit)? = null,
) {
    var destination by rememberSaveable { mutableStateOf(Destination.ARGUS) }
    var page by rememberSaveable { mutableStateOf(Page.ROOT) }
    var settingsSource by rememberSaveable { mutableStateOf(Page.ROOT) }
    var dialog by rememberSaveable { mutableStateOf<Int?>(null) }
    val sessionEnabled = sessionState != null && sessionState.status != SessionStatus.DISABLED
    // Authenticated drafts never enter Android saved state. The controller owns retirement;
    // refresh keeps its epoch, while sign-out/switch creates a fresh one immediately.
    val draft = if (sessionEnabled) {
        remember(sessionState?.ownershipEpoch, sessionState?.status == SessionStatus.SIGNED_OUT) {
            mutableStateOf("")
        }
    } else {
        rememberSaveable { mutableStateOf("") }
    }
    val composerEnabled = !sessionEnabled || sessionState?.status == SessionStatus.SIGNED_OUT ||
        (sessionState?.status == SessionStatus.SIGNED_IN && sessionState.profile != null)
    val composer = if (composerEnabled) draft.value else ""
    val focus = LocalFocusManager.current
    val keyboardVisible = WindowInsets.ime.getBottom(LocalDensity.current) > 0
    var compactNavigation by remember(destination) { mutableStateOf(false) }
    val navigationScroll = remember(destination) {
        object : NestedScrollConnection {
            private var distance = 0f
            override fun onPostScroll(consumed: Offset, available: Offset, source: NestedScrollSource): Offset {
                if (source != NestedScrollSource.UserInput) return Offset.Zero
                if ((distance < 0) != (consumed.y < 0)) distance = 0f
                distance += consumed.y
                if (distance < -90f) compactNavigation = true
                if (distance > 35f) compactNavigation = false
                return Offset.Zero
            }
        }
    }
    val requireRegistration = {
        dialog = when (sessionState?.status) {
            SessionStatus.SIGNED_IN -> R.string.session_financial_boundary
            null, SessionStatus.DISABLED -> R.string.registration_body
            else -> R.string.session_registration_body
        }
    }
    val unavailable = { dialog = R.string.unavailable_body }
    val back = {
        page = when (page) {
            Page.PREFERENCES, Page.SESSION -> Page.SETTINGS
            Page.SETTINGS -> settingsSource
            else -> Page.ROOT
        }
    }

    BackHandler(enabled = page != Page.ROOT || destination != Destination.ARGUS) {
        if (page != Page.ROOT) back() else destination = Destination.ARGUS
    }

    CompositionLocalProvider(LocalSessionEnabled provides
        (sessionState != null && sessionState.status != SessionStatus.DISABLED)) {
    Surface(Modifier.fillMaxSize().testTag("app_surface")) {
        Column(Modifier.fillMaxSize().systemBarsPadding().imePadding()) {
            AppHeader(destination, page, back,
                onRecents = { page = Page.RECENTS },
                onTemporary = { dialog = if (sessionState != null && sessionState.status != SessionStatus.DISABLED)
                    R.string.session_temporary_body else R.string.temporary_body },
                onUpdates = { page = Page.UPDATES },
                onSettings = { settingsSource = Page.ROOT; page = Page.SETTINGS })
            Box(Modifier.weight(1f).fillMaxWidth().nestedScroll(navigationScroll)) {
                when (page) {
                    Page.SETTINGS -> SettingsPage(
                        onPreferences = { page = Page.PREFERENCES }, unavailable = unavailable,
                        sessionState = sessionState?.takeUnless { it.status == SessionStatus.DISABLED },
                        onSession = { page = Page.SESSION },
                    )
                    Page.SESSION -> sessionState?.let { state ->
                        SessionPage(state, onSignIn, onSignOut, onSessionRetry, onRecovery)
                    }
                    Page.PREFERENCES -> PreferencesPage(appearance, onAppearanceChange)
                    Page.UPDATES -> SecondarySamplePage(R.string.updates_empty, R.string.updates_body)
                    Page.RECENTS -> RecentsPage(onSettings = {
                        settingsSource = Page.RECENTS; page = Page.SETTINGS
                    })
                    Page.ROOT -> when (destination) {
                        Destination.ARGUS -> ChatPage(
                            composer, { if (composerEnabled) draft.value = it }, requireRegistration,
                            onSend = { focus.clearFocus(); dialog = R.string.chat_disconnected },
                            unavailable = unavailable, composerEnabled = composerEnabled,
                        )
                        else -> key(destination) {
                            EcosystemPage(destination, requireRegistration, unavailable)
                        }
                    }
                }
            }
            if (page == Page.ROOT && !keyboardVisible) {
                FloatingNavigation(destination, compactNavigation) {
                    destination = it; compactNavigation = false; focus.clearFocus()
                }
            }
        }
    }
    }
    dialog?.let { body ->
        val registrationBoundary = body == R.string.registration_body || body == R.string.session_registration_body
        AlertDialog(
            modifier = Modifier.testTag(
                if (registrationBoundary) "registration_dialog" else "sample_dialog",
            ),
            onDismissRequest = { dialog = null },
            title = { Text(stringResource(
                if (registrationBoundary) R.string.registration_title
                else R.string.sample_title,
            )) },
            text = { Text(stringResource(body)) },
            confirmButton = { TextButton(onClick = { dialog = null }) {
                Text(stringResource(R.string.got_it))
            } },
        )
    }
}

@Composable
private fun AppHeader(
    destination: Destination, page: Page, onBack: () -> Unit,
    onRecents: () -> Unit, onTemporary: () -> Unit,
    onUpdates: () -> Unit, onSettings: () -> Unit,
) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically) {
        when {
            page != Page.ROOT -> {
                QuietIcon(ArgusIcons.Back, R.string.back, onBack)
                Text(stringResource(page.title), Modifier.weight(1f),
                    style = MaterialTheme.typography.titleLarge)
            }
            destination == Destination.ARGUS -> {
                Row {
                    QuietIcon(ArgusIcons.Recents, R.string.recents, onRecents)
                    // The empty state reserves New's slot; no active chat exists in this sample.
                    Spacer(Modifier.size(48.dp))
                }
                Spacer(Modifier.weight(1f))
                QuietIcon(ArgusIcons.Temporary, R.string.temporary_chat, onTemporary)
            }
            else -> {
                Text(stringResource(if (destination == Destination.HOME)
                    R.string.argus_wordmark else destination.title),
                    Modifier.weight(1f).padding(start = 12.dp),
                    style = MaterialTheme.typography.titleLarge)
                QuietIcon(ArgusIcons.Updates, R.string.updates, onUpdates)
                QuietIcon(ArgusIcons.Profile, R.string.profile_settings, onSettings,
                    Modifier.testTag("settings"))
            }
        }
    }
}

@Composable
private fun FloatingNavigation(selected: Destination, compact: Boolean, onSelect: (Destination) -> Unit) {
    Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
    Surface(
        modifier = Modifier.padding(horizontal = 24.dp, vertical = 10.dp)
            .then(if (compact) Modifier.widthIn(max = 270.dp) else Modifier)
            .fillMaxWidth().testTag(if (compact) "navigation_compact" else "navigation_expanded"),
        shape = RoundedCornerShape(40.dp), color = MaterialTheme.colorScheme.surfaceContainer,
        shadowElevation = 6.dp,
    ) {
        Row(Modifier.fillMaxWidth().selectableGroup().padding(6.dp),
            horizontalArrangement = Arrangement.SpaceEvenly) {
            Destination.entries.forEach { destination ->
                Box(
                    Modifier.size(if (compact) 48.dp else 52.dp)
                        .clip(CircleShape)
                        .background(if (destination == selected) MaterialTheme.colorScheme.surfaceContainerHighest
                            else MaterialTheme.colorScheme.surfaceContainer, CircleShape)
                        .selectable(selected = destination == selected, role = Role.Tab,
                            onClick = { onSelect(destination) })
                        .testTag("tab_${destination.name}"),
                    contentAlignment = Alignment.Center,
                ) {
                    val label = stringResource(
                        if (destination == Destination.ARGUS) R.string.ask_argus else destination.title,
                    )
                    if (destination == Destination.ARGUS) {
                        Icon(painterResource(R.drawable.argus_mark), label, Modifier.size(26.dp))
                    } else {
                        val icon = when (destination) {
                            Destination.HOME -> ArgusIcons.Home
                            Destination.ACCOUNTS -> ArgusIcons.Accounts
                            Destination.PLAN -> ArgusIcons.Plan
                            else -> ArgusIcons.Search
                        }
                        Icon(icon, label, Modifier.size(23.dp))
                    }
                }
            }
        }
    }
    }
}
