package ai.argus.foundation

import android.content.res.Configuration
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.toPixelMap
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertContentDescriptionEquals
import androidx.compose.ui.test.assertHasClickAction
import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.assertWidthIsAtLeast
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import java.io.File
import kotlin.math.abs
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.ExternalResource
import org.junit.rules.RuleChain
import org.junit.runner.RunWith

/** Disconnected sample tests. They never invoke Argus, an auth provider, or a market-data API. */
@RunWith(AndroidJUnit4::class)
class FoundationTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val device = UiDevice.getInstance(instrumentation)
    private val compose = createAndroidComposeRule<MainActivity>()
    private val preferenceIsolation = object : ExternalResource() {
        private var original = Appearance.SYSTEM
        override fun before() {
            original = AppearanceStore(context).selected
            AppearanceStore(context).select(Appearance.SYSTEM)
        }
        override fun after() {
            AppearanceStore(context).select(original)
        }
    }

    @get:Rule
    val rules: RuleChain = RuleChain.outerRule(preferenceIsolation).around(compose)

    @Test
    fun startsInChatAndAllFiveTabsHaveOrderedAccessibleTargets() {
        compose.onNodeWithTag("tab_ARGUS").assertIsSelected()
        val destinations = listOf(
            "HOME" to R.string.home,
            "ACCOUNTS" to R.string.accounts,
            "ARGUS" to R.string.ask_argus,
            "PLAN" to R.string.plan,
            "SEARCH" to R.string.search,
        )
        var previousRight = Float.NEGATIVE_INFINITY
        destinations.forEach { (name, label) ->
            val tab = compose.onNodeWithTag("tab_$name")
                .assertHasClickAction()
                .assertWidthIsAtLeast(48.dp).assertHeightIsAtLeast(48.dp)
                .assert(SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Tab))
                .assertContentDescriptionEquals(context.getString(label))
            val bounds = tab.fetchSemanticsNode().boundsInRoot
            assertTrue("$name must follow the previous destination", bounds.left >= previousRight)
            previousRight = bounds.right
            tab.performClick().assertIsSelected()
            compose.onNodeWithTag("sample_notice").assertIsDisplayed()
            screenshot("tab_${name.lowercase()}")
        }
    }

    @Test
    fun everyDirectEcosystemActionRequiresRegistrationAndBackOnlyDismissesDialog() {
        listOf("HOME", "ACCOUNTS", "PLAN", "SEARCH").forEach { destination ->
            compose.onNodeWithTag("tab_$destination").performClick()
            compose.onNodeWithTag("guest_action_direct").performScrollTo().performClick()
            assertRegistrationBoundary()
            screenshot("registration_${destination.lowercase()}")
            device.pressBack()
            compose.onNodeWithTag("registration_dialog").assertDoesNotExist()
            compose.onNodeWithTag("tab_$destination").assertIsSelected()
            device.pressBack()
            compose.onNodeWithTag("tab_ARGUS").assertIsSelected()
        }
    }

    @Test
    fun chatEcosystemActionUsesTheSameRegistrationBoundary() {
        compose.onNodeWithTag("guest_action_chat").performScrollTo().performClick()
        assertRegistrationBoundary()
        screenshot("registration_chat")
        device.pressBack()
        compose.onNodeWithTag("registration_dialog").assertDoesNotExist()
        compose.onNodeWithTag("tab_ARGUS").assertIsSelected()
    }

    @Test
    fun financeChatAcceptsInputButHonestlyDisclosesDisconnectedExecution() {
        val message = "What does compound interest mean?"
        compose.onNodeWithTag("composer").performScrollTo().performTextInput(message)
        compose.onNodeWithTag("composer").assertTextContains(message)
        device.pressBack() // Dismiss the IME, retaining the draft.
        compose.onNodeWithTag("composer").assertTextContains(message)
        compose.onNodeWithContentDescription(context.getString(R.string.send_message))
            .performScrollTo().performClick()
        compose.onNodeWithText(context.getString(R.string.chat_disconnected)).assertIsDisplayed()
        compose.onNodeWithTag("registration_dialog").assertDoesNotExist()
        screenshot("finance_chat_disconnected")
    }

    @Test
    fun settingsBackReturnsThroughPreferencesToItsOriginatingTab() {
        compose.onNodeWithTag("tab_ACCOUNTS").performClick()
        compose.onNodeWithTag("settings").performClick()
        compose.onNodeWithTag("preferences").performScrollTo().performClick()
        compose.onNodeWithTag("appearance_SYSTEM").assertIsSelected()
        device.pressBack()
        compose.onNodeWithTag("preferences").assertIsDisplayed()
        device.pressBack()
        compose.onNodeWithTag("tab_ACCOUNTS").assertIsSelected()
        device.pressBack()
        compose.onNodeWithTag("tab_ARGUS").assertIsSelected()
    }

    @Test
    fun everyAppearanceChoiceSurvivesActivityRecreationAndStoreReload() {
        openPreferences()
        Appearance.entries.forEach { appearance ->
            val tag = "appearance_${appearance.name}"
            compose.onNodeWithTag(tag).performScrollTo()
                .assertWidthIsAtLeast(48.dp).assertHeightIsAtLeast(48.dp)
                .performClick().assertIsSelected()
            compose.activityRule.scenario.recreate()
            compose.onNodeWithTag(tag).assertIsSelected()
            assertEquals(appearance, AppearanceStore(context).selected)
            screenshot("appearance_${appearance.name.lowercase()}")
        }
    }

    @Test
    fun systemAppearanceRespondsToSystemChangesWhileExplicitLightRemainsLight() {
        // This is an emulator-only setting change. Always restore the original device mode.
        val original = device.executeShellCommand("cmd uimode night").substringAfter(":").trim()
        assertTrue("Unsupported night-mode response: $original", original in setOf("yes", "no", "auto", "custom"))
        try {
            openPreferences()
            compose.onNodeWithTag("appearance_SYSTEM").performScrollTo().performClick()
            setSystemNight(false)
            val light = surfaceLuminance()
            setSystemNight(true)
            val dark = surfaceLuminance()
            assertTrue("System dark should visibly darken the app surface", light - dark > 0.5f)
            screenshot("appearance_system_dark")
            compose.onNodeWithTag("appearance_LIGHT").performScrollTo().performClick()
            val forcedLight = surfaceLuminance()
            assertTrue("Light should override system dark", forcedLight - dark > 0.5f)
            setSystemNight(false)
            assertTrue("System changes must preserve explicit Light", abs(forcedLight - surfaceLuminance()) < 0.01f)
        } finally {
            device.executeShellCommand("cmd uimode night $original")
        }
    }

    @Test
    fun updatesBackReturnsToTheOriginatingTab() {
        compose.onNodeWithTag("tab_PLAN").performClick()
        compose.onNodeWithContentDescription(context.getString(R.string.updates)).performClick()
        compose.onNodeWithText(context.getString(R.string.updates_empty)).assertIsDisplayed()
        screenshot("updates")
        device.pressBack()
        compose.onNodeWithTag("tab_PLAN").assertIsSelected()
    }

    @Test
    fun backFromRootChatLeavesTheApp() {
        compose.onNodeWithTag("tab_ARGUS").assertIsSelected()
        device.pressBack()
        assertTrue("Root Back should leave the foreground app",
            device.wait(Until.gone(By.pkg(context.packageName)), 5_000))
    }

    private fun openPreferences() {
        compose.onNodeWithTag("tab_HOME").performClick()
        compose.onNodeWithTag("settings").performClick()
        compose.onNodeWithTag("preferences").performScrollTo().performClick()
    }

    private fun assertRegistrationBoundary() {
        compose.onNodeWithTag("registration_dialog").assertIsDisplayed()
        compose.onNodeWithText(context.getString(R.string.registration_body)).assertIsDisplayed()
    }

    private fun setSystemNight(dark: Boolean) {
        device.executeShellCommand("cmd uimode night ${if (dark) "yes" else "no"}")
        compose.waitUntil(timeoutMillis = 10_000) {
            val actual = compose.activity.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK
            actual == if (dark) Configuration.UI_MODE_NIGHT_YES else Configuration.UI_MODE_NIGHT_NO
        }
        compose.waitForIdle()
    }

    private fun surfaceLuminance(): Float {
        compose.waitForIdle()
        return compose.onNodeWithTag("app_surface").captureToImage().toPixelMap()[2, 2].luminance()
    }

    private fun screenshot(name: String) {
        // Let the native press ripple settle before retaining visual evidence.
        compose.mainClock.advanceTimeBy(1_000)
        compose.waitForIdle()
        device.waitForIdle()
        val output = File(context.getExternalFilesDir("evidence"), "${device.displayWidth}x${device.displayHeight}")
        assertTrue("Could not create evidence directory", output.isDirectory || output.mkdirs())
        assertTrue("Screenshot failed: $name", device.takeScreenshot(File(output, "$name.png")))
    }
}
