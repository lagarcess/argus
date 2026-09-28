package ai.argus.foundation

import android.app.Activity
import android.app.Instrumentation
import android.content.Intent
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.text.AnnotatedString
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import org.junit.Assert.assertEquals
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Opt-in disposable-stack acceptance. The runner supplies synthetic users; never print inputs. */
@RunWith(AndroidJUnit4::class)
class RegisteredSessionLocalTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun registeredAccountsSwitchOnlyAfterSignOutAndRecoveryStaysInBrowser() {
        assumeTrue("Requires the opt-in local build", BuildConfig.LOCAL_AUTH_ENABLED)
        val arguments = InstrumentationRegistry.getArguments()
        val email = arguments.getString("authEmail")
        val password = arguments.getString("authPassword")
        val secondEmail = arguments.getString("authSecondEmail")
        val secondPassword = arguments.getString("authSecondPassword")
        assumeTrue("Requires two synthetic local users",
            listOf(email, password, secondEmail, secondPassword).all { !it.isNullOrBlank() })
        val owner = compose.activity.application as ArgusApplication
        assumeTrue("Requires validated local configuration", owner.authEnvironment != null)

        compose.onNodeWithTag("tab_ARGUS").assertIsDisplayed()
        compose.onNodeWithTag("tab_HOME").performClick()
        compose.onNodeWithTag("settings").performClick()
        compose.onNodeWithTag("session_entry").performClick()
        waitFor("session_submit")
        signIn(requireNotNull(email), requireNotNull(password))
        compose.onNodeWithTag("session_email").assertTextEquals(email)
        compose.onNodeWithTag("session_password_input").assertDoesNotExist()
        openChatFromSession()
        compose.onNodeWithTag("composer").performScrollTo().performTextInput("Synthetic account A draft")
        UiDevice.getInstance(InstrumentationRegistry.getInstrumentation()).pressBack()
        compose.waitForIdle()
        openSessionFromChat()

        compose.onNodeWithTag("session_switch").performScrollTo().performClick()
        waitFor("session_submit")
        compose.onNodeWithText(email).assertDoesNotExist()
        assertEmptyPassword()
        signIn(requireNotNull(secondEmail), requireNotNull(secondPassword))
        compose.onNodeWithTag("session_email").assertTextEquals(secondEmail)
        compose.onNodeWithText(email).assertDoesNotExist()
        openChatFromSession()
        compose.onNodeWithTag("composer")
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText, AnnotatedString("")))
        openSessionFromChat()
        compose.onNodeWithTag("session_sign_out").performScrollTo().performClick()
        waitFor("session_submit")
        compose.onNodeWithText(secondEmail).assertDoesNotExist()
        assertEmptyPassword()

        assertBrowserRecoveryIntent(requireNotNull(owner.authEnvironment).recoveryUrl)
        assertEmptyPassword()
    }

    private fun openChatFromSession() {
        val device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
        device.pressBack()
        compose.waitForIdle()
        device.pressBack()
        compose.waitForIdle()
        compose.onNodeWithTag("tab_ARGUS").performClick()
    }

    private fun openSessionFromChat() {
        compose.onNodeWithTag("tab_HOME").performClick()
        compose.onNodeWithTag("settings").performClick()
        compose.onNodeWithTag("session_entry").performClick()
    }

    private fun signIn(email: String, password: String) {
        compose.onNodeWithTag("session_email_input").performScrollTo().performTextInput(email)
        compose.onNodeWithTag("session_password_input").performScrollTo().performTextInput(password)
        compose.onNodeWithTag("session_submit").performScrollTo().performClick()
        waitFor("session_verified")
    }

    private fun assertEmptyPassword() {
        compose.onNodeWithTag("session_password_input")
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText, AnnotatedString("")))
    }

    private fun waitFor(tag: String) {
        compose.waitUntil(30_000) { compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() }
    }

    private fun assertBrowserRecoveryIntent(expectedUrl: String) {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        var action: String? = null
        var destination: String? = null
        val monitor = object : Instrumentation.ActivityMonitor() {
            override fun onStartActivity(intent: Intent): Instrumentation.ActivityResult? {
                if (intent.action != Intent.ACTION_VIEW) return null
                action = intent.action
                destination = intent.dataString
                return Instrumentation.ActivityResult(Activity.RESULT_CANCELED, null)
            }
        }
        instrumentation.addMonitor(monitor)
        try {
            compose.onNodeWithTag("session_recovery").performScrollTo().performClick()
            compose.runOnIdle {
                assertEquals(Intent.ACTION_VIEW, action)
                assertEquals(expectedUrl, destination)
            }
        } finally {
            instrumentation.removeMonitor(monitor)
        }
    }
}
