package ai.argus.foundation

import android.content.res.Configuration
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertHasClickAction
import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.junit4.StateRestorationTester
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import java.io.File
import ai.argus.foundation.auth.SessionProblem
import ai.argus.foundation.auth.SessionProfile
import ai.argus.foundation.auth.SessionStatus
import ai.argus.foundation.auth.SessionUiState
import ai.argus.foundation.ui.ArgusApp
import ai.argus.foundation.ui.SessionPage
import ai.argus.foundation.ui.SessionLocale
import java.util.Locale
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Synthetic state tests only. No credentials or real auth operations are dispatched. */
@RunWith(AndroidJUnit4::class)
class SessionUiTest {
    @get:Rule val compose = createComposeRule()

    @Test fun verifiedProfileLanguageHydratesWithoutResettingNavigation() {
        val state = mutableStateOf(SessionUiState(SessionStatus.SIGNED_OUT))
        compose.setContent {
            SessionLocale(state.value) {
                ArgusTheme(false) { ArgusApp(Appearance.LIGHT, {}, sessionState = state.value) }
            }
        }
        compose.onNodeWithTag("tab_HOME").performClick()
        compose.onNodeWithTag("settings").performClick()
        compose.onNodeWithTag("session_entry").performClick()
        compose.runOnIdle {
            state.value = SessionUiState(SessionStatus.SIGNED_IN,
                SessionProfile("synthetic-id", null, "Synthetic User", "es-419", "es-DO"))
        }
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val config = Configuration(context.resources.configuration).apply {
            setLocale(Locale.forLanguageTag("es-419"))
        }
        val expected = context.createConfigurationContext(config).getString(R.string.session_verified)
        compose.onNodeWithText(expected).assertIsDisplayed()
        compose.onNodeWithTag("session_page").assertIsDisplayed()
        compose.onNodeWithTag("tab_ARGUS").assertDoesNotExist()
    }

    @Test fun disabledSessionKeepsOptionalSampleEntry() {
        compose.setContent { ArgusTheme(false) { ArgusApp(Appearance.LIGHT, {}) } }
        compose.onNodeWithTag("tab_ARGUS").assertIsDisplayed()
        compose.onNodeWithTag("tab_HOME").performClick()
        compose.onNodeWithTag("settings").performClick()
        compose.onNodeWithTag("session_entry").assertDoesNotExist()
        compose.onNodeWithTag("preferences").assertIsDisplayed()
    }

    @Test fun passwordIsMaskedAndClearsImmediatelyOnSubmit() {
        var submissions = 0
        var receivedSyntheticInput = false
        compose.setContent {
            ArgusTheme(false) {
                SessionPage(SessionUiState(SessionStatus.SIGNED_OUT),
                    onSignIn = { email, password ->
                        submissions++
                        receivedSyntheticInput = email == "synthetic@example.test" && password.isNotEmpty()
                    }, onSignOut = {}, onRetry = {}, onRecovery = null)
            }
        }
        compose.onNodeWithTag("session_submit").assertIsNotEnabled()
        compose.onNodeWithTag("session_email_input").performTextInput("synthetic@example.test")
        compose.onNodeWithTag("session_password_input").performTextInput("synthetic-test-only")
        compose.onNodeWithTag("session_password_input")
            .assert(SemanticsMatcher.keyIsDefined(SemanticsProperties.Password))
        compose.onNodeWithTag("session_submit").performScrollTo().performClick()
        compose.onNodeWithTag("session_password_input")
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText, AnnotatedString("")))
        compose.runOnIdle { assertEquals(1, submissions); assertTrue(receivedSyntheticInput) }
        compose.onNodeWithTag("session_submit").assertIsNotEnabled()
    }

    @Test fun passwordClearsOnExitAndBeforeBrowserRecovery() {
        val visible = mutableStateOf(true)
        var recoveries = 0
        compose.setContent {
            ArgusTheme(false) {
                if (visible.value) SessionPage(SessionUiState(SessionStatus.SIGNED_OUT),
                    onSignIn = { _, _ -> }, onSignOut = {}, onRetry = {},
                    onRecovery = { recoveries++ })
            }
        }
        compose.onNodeWithTag("session_password_input").performTextInput("synthetic-test-only")
        compose.onNodeWithTag("session_recovery").performScrollTo().performClick()
        compose.onNodeWithTag("session_password_input")
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText, AnnotatedString("")))
        compose.runOnIdle { assertEquals(1, recoveries) }
        compose.onNodeWithTag("session_password_input").performScrollTo().performTextInput("another-test-value")
        compose.runOnIdle { visible.value = false }
        compose.onNodeWithTag("session_password_input").assertDoesNotExist()
        compose.runOnIdle { visible.value = true }
        compose.onNodeWithTag("session_password_input")
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText, AnnotatedString("")))
    }

    @Test fun signOutRetiresProfileAndCannotOfferLoginBeforeRevocationCompletes() {
        val profile = SessionProfile("synthetic-id", "synthetic@example.test", "Synthetic User", "en", "en-US")
        val state = mutableStateOf(SessionUiState(SessionStatus.SIGNED_IN, profile = profile))
        var signOutCalls = 0
        compose.setContent {
            ArgusTheme(false) {
                SessionPage(state.value, onSignIn = { _, _ -> },
                    onSignOut = { signOutCalls++; state.value = SessionUiState(SessionStatus.WORKING) },
                    onRetry = {}, onRecovery = null)
            }
        }
        compose.onNodeWithTag("session_email").assertIsDisplayed()
        compose.onNodeWithTag("session_switch").performScrollTo().performClick()
        compose.onNodeWithTag("session_email").assertDoesNotExist()
        compose.onNodeWithTag("session_password_input").assertDoesNotExist()
        compose.runOnIdle {
            state.value = SessionUiState(SessionStatus.REVOCATION_FAILED, problem = SessionProblem.REVOCATION)
        }
        compose.onNodeWithTag("session_retry_sign_out").assertHasClickAction()
            .assertHeightIsAtLeast(48.dp).performScrollTo().performClick()
        compose.runOnIdle { assertEquals(2, signOutCalls) }
        compose.onNodeWithTag("session_password_input").assertDoesNotExist()
    }

    @Test fun guestAndVerificationFailureNeverRenderPrivateProfileOrSignIn() {
        val state = mutableStateOf(SessionUiState(SessionStatus.GUEST_PRESERVED,
            problem = SessionProblem.UNSUPPORTED_GUEST))
        var retries = 0
        compose.setContent {
            ArgusTheme(false) {
                SessionPage(state.value, onSignIn = { _, _ -> }, onSignOut = {},
                    onRetry = { retries++ }, onRecovery = null)
            }
        }
        compose.onNodeWithTag("session_guest_boundary").assertIsDisplayed()
        compose.onNodeWithTag("session_password_input").assertDoesNotExist()
        compose.onNodeWithTag("session_sign_out").assertDoesNotExist()
        compose.runOnIdle {
            state.value = SessionUiState(SessionStatus.RECOVERY_REQUIRED,
                problem = SessionProblem.VERIFICATION_UNAVAILABLE)
        }
        val text = InstrumentationRegistry.getInstrumentation().targetContext
            .getString(R.string.session_error_verification)
        compose.onNodeWithText(text).assertIsDisplayed()
        compose.onNodeWithTag("session_email").assertDoesNotExist()
        compose.onNodeWithTag("session_retry").performScrollTo().performClick()
        compose.runOnIdle { assertEquals(1, retries) }
    }

    @Test fun draftSurvivesSameOwnerRefreshButIsHiddenUntilVerifiedAndRetiresOnSwitch() {
        val accountA = SessionProfile("synthetic-a", null, "Synthetic A", "en", "en-US")
        val accountB = accountA.copy(id = "synthetic-b", displayName = "Synthetic B")
        val state = mutableStateOf(SessionUiState(SessionStatus.SIGNED_IN, accountA, ownershipEpoch = 1))
        compose.setContent { ArgusTheme(false) { ArgusApp(Appearance.LIGHT, {}, sessionState = state.value) } }
        compose.onNodeWithTag("composer").performScrollTo().performTextInput("Synthetic private draft A")
        compose.runOnIdle { state.value = SessionUiState(SessionStatus.WORKING, ownershipEpoch = 1) }
        assertDraft("")
        compose.onNodeWithTag("composer").assertIsNotEnabled()
        compose.runOnIdle {
            state.value = SessionUiState(SessionStatus.RECOVERY_REQUIRED,
                problem = SessionProblem.NETWORK, ownershipEpoch = 1)
        }
        assertDraft("")
        compose.runOnIdle { state.value = SessionUiState(SessionStatus.SIGNED_IN, accountA, ownershipEpoch = 1) }
        assertDraft("Synthetic private draft A")
        // Sign-out retires the canonical ownership epoch before server revocation finishes.
        compose.runOnIdle { state.value = SessionUiState(SessionStatus.WORKING, ownershipEpoch = 2) }
        assertDraft("")
        compose.runOnIdle {
            state.value = SessionUiState(SessionStatus.REVOCATION_FAILED,
                problem = SessionProblem.REVOCATION, ownershipEpoch = 2)
        }
        assertDraft("")
        compose.runOnIdle { state.value = SessionUiState(SessionStatus.SIGNED_OUT, ownershipEpoch = 2) }
        compose.runOnIdle { state.value = SessionUiState(SessionStatus.SIGNED_IN, accountB, ownershipEpoch = 3) }
        assertDraft("")
        // Signing A back in later must not resurrect the retired draft either.
        compose.runOnIdle { state.value = SessionUiState(SessionStatus.SIGNED_IN, accountA, ownershipEpoch = 4) }
        assertDraft("")
    }

    @Test fun rejectedSessionClearsDraftEvenWithoutAnEpochChange() {
        val profile = SessionProfile("synthetic-a", null, null, "en", "en-US")
        val state = mutableStateOf(SessionUiState(SessionStatus.SIGNED_IN, profile, ownershipEpoch = 1))
        compose.setContent { ArgusTheme(false) { ArgusApp(Appearance.LIGHT, {}, sessionState = state.value) } }
        compose.onNodeWithTag("composer").performScrollTo().performTextInput("Synthetic rejected draft")
        compose.runOnIdle { state.value = SessionUiState(SessionStatus.SIGNED_OUT, ownershipEpoch = 1) }
        assertDraft("")
        compose.runOnIdle { state.value = SessionUiState(SessionStatus.SIGNED_IN, profile, ownershipEpoch = 1) }
        assertDraft("")
    }

    @Test fun localAuthDraftDoesNotEnterRestoredSavedState() {
        val profile = SessionProfile("synthetic-a", null, null, "en", "en-US")
        val state = mutableStateOf(SessionUiState(SessionStatus.SIGNED_IN, profile, ownershipEpoch = 1))
        val restoration = StateRestorationTester(compose)
        restoration.setContent { ArgusTheme(false) { ArgusApp(Appearance.LIGHT, {}, sessionState = state.value) } }
        compose.onNodeWithTag("composer").performScrollTo().performTextInput("Synthetic private restored draft")
        restoration.emulateSavedInstanceStateRestore()
        assertDraft("")
    }

    @Test fun sanitizedSessionScreens() {
        val state = mutableStateOf(SessionUiState(SessionStatus.SIGNED_OUT))
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val english = Configuration(context.resources.configuration).apply { setLocale(Locale.ENGLISH) }
        val englishContext = context.createConfigurationContext(english)
        compose.setContent {
            CompositionLocalProvider(LocalContext provides englishContext, LocalConfiguration provides english) {
                SessionLocale(state.value) {
                    ArgusTheme(false) { ArgusApp(Appearance.LIGHT, {}, sessionState = state.value, onRecovery = {}) }
                }
            }
        }
        compose.onNodeWithTag("tab_HOME").performClick()
        compose.onNodeWithTag("settings").performClick()
        compose.onNodeWithTag("session_entry").performClick()
        compose.onNodeWithTag("session_submit").assertIsNotEnabled()
        screenshot("session-en-signed-out")
        compose.runOnIdle {
            state.value = SessionUiState(SessionStatus.SIGNED_IN,
                SessionProfile("synthetic-capture", "sample@example.test", "Perfil de muestra", "es-419", "es-DO"),
                ownershipEpoch = 1)
        }
        compose.onNodeWithTag("session_verified").assertIsDisplayed()
        screenshot("session-es-verified")
        compose.runOnIdle {
            state.value = SessionUiState(SessionStatus.REVOCATION_FAILED,
                problem = SessionProblem.REVOCATION, ownershipEpoch = 2)
        }
        compose.onNodeWithTag("session_revocation_pending").assertIsDisplayed()
        screenshot("session-en-revocation-failed")
    }

    private fun assertDraft(expected: String) {
        compose.onNodeWithTag("composer")
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText, AnnotatedString(expected)))
    }

    private fun screenshot(name: String) {
        compose.mainClock.advanceTimeBy(1_000)
        compose.waitForIdle()
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val device = UiDevice.getInstance(instrumentation)
        device.waitForIdle()
        val output = File(instrumentation.targetContext.getExternalFilesDir("evidence"),
            "${device.displayWidth}x${device.displayHeight}")
        assertTrue("Could not create evidence directory", output.isDirectory || output.mkdirs())
        assertTrue("Screenshot failed: $name", device.takeScreenshot(File(output, "$name.png")))
    }
}
