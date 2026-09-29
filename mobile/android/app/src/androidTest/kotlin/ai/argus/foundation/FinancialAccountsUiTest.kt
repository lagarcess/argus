package ai.argus.foundation

import ai.argus.foundation.accounts.ArgusAccountsApi
import ai.argus.foundation.auth.SessionStatus
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextReplacement
import androidx.compose.ui.text.AnnotatedString
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import java.io.File
import java.util.UUID
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Real registered session and API; the host owns local services, viewport and font scale. */
@RunWith(AndroidJUnit4::class)
class FinancialAccountsUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val args get() = InstrumentationRegistry.getArguments()
    private val application get() = compose.activity.application as ArgusApplication
    private val session get() = requireNotNull(application.sessionController)
    private val device get() = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())

    @Test fun nativeCreateReopenEditCorrectArchiveRestoreAndUnknown() {
        assumeTrue(BuildConfig.LOCAL_AUTH_ENABLED)
        assumeTrue(args.containsKey("email") && args.containsKey("password"))
        args.getString("accountsTheme")?.let { value ->
            val appearance = Appearance.valueOf(value.uppercase())
            AppearanceStore(compose.activity).select(appearance)
            compose.activityRule.scenario.recreate()
        }
        compose.onNodeWithTag("tab_ACCOUNTS").performClick()
        waitFor("accounts_sign_in")
        click("accounts_sign_in")
        waitFor("session_submit")
        input("session_email_input", requireNotNull(args.getString("email")))
        input("session_password_input", requireNotNull(args.getString("password")))
        click("session_submit")
        waitFor("account_create")
        assertEquals(SessionStatus.SIGNED_IN, session.state.value.status)
        screenshot("list")

        val suffix = UUID.randomUUID().toString().take(6)
        val name = "Synthetic savings $suffix"
        click("account_create")
        listOf("account_date", "account_time", "account_time_zone", "account_share", "account_share_change")
            .forEach { compose.onNodeWithTag(it).assertDoesNotExist() }
        input("account_nickname", name)
        input("account_currency", "USD")
        input("account_amount", "0")
        screenshot("create-keyboard")
        device.pressBack()
        click("account_save")
        waitFor("account_edit")
        compose.onNodeWithTag("account_name").assertTextEquals(name)
        val created = serverAccount(name)
        assertEquals("known", created.balance.state)
        assertEquals("0.00", created.balance.amount)
        screenshot("known-zero")

        click("account_back")
        click("account_row_${created.id}")
        waitFor("account_edit")
        click("account_edit")
        val editedName = "Synthetic reserve $suffix"
        input("account_nickname", editedName)
        input("account_currency", "JPY")
        click("account_save")
        waitFor("accounts_problem")
        compose.onNodeWithTag("account_nickname")
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText, AnnotatedString(editedName)))
        assertEquals("USD", serverAccount(name).currency)
        input("account_currency", "USD")
        click("account_save")
        waitFor("account_edit")
        compose.onNodeWithTag("account_name").assertTextEquals(editedName)
        click("account_opening")
        input("account_amount", "12.34")
        click("account_save") // Corrections require a reason; keep the person's amount.
        waitFor("accounts_problem")
        compose.onNodeWithTag("account_amount")
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText, AnnotatedString("12.34")))
        screenshot("correction-error")
        input("account_reason", "Correct synthetic starting balance")
        click("account_save")
        waitFor("account_edit")
        assertEquals("12.34", serverAccount(editedName).balance.amount)
        assertEquals(2, serverAccount(editedName).opening?.revision)
        screenshot("corrected-history")
        click("account_archive")
        click("account_save")
        waitFor("account_edit")
        assertTrue(serverAccount(editedName).archived)
        click("account_back")
        compose.onNodeWithTag("account_row_${created.id}").assertDoesNotExist()
        click("account_manage")
        click("account_row_${created.id}")
        waitFor("account_edit")
        click("account_archive")
        click("account_save")
        waitFor("account_edit")
        assertEquals(false, serverAccount(editedName).archived)
        click("account_back")
        click("account_manage") // Return from Manage accounts to active accounts.
        click("account_create")
        val unknownName = "Synthetic unknown $suffix"
        input("account_nickname", unknownName)
        click("account_known")
        click("account_save")
        waitFor("account_edit")
        assertEquals("unknown", serverAccount(unknownName).balance.state)
        assertEquals(null, serverAccount(unknownName).balance.amount)
        screenshot("unknown")
        click("account_back")
        screenshot("active-list")

        click("account_create")
        val assetName = "Synthetic shared property $suffix"
        input("account_nickname", assetName)
        click("account_type")
        compose.onNodeWithTag("account_type_property").performScrollTo().performClick()
        compose.onNodeWithTag("account_share").assertDoesNotExist()
        click("account_share_change")
        compose.onNodeWithTag("account_share_half").performClick()
        compose.onNodeWithTag("account_share").assertDoesNotExist()
        input("account_currency", "USD")
        input("account_amount", "1000")
        click("account_save")
        waitFor("account_edit")
        val asset = serverAccount(assetName)
        assertEquals("property", asset.type)
        assertEquals(5000, asset.ownershipShareBps)
        assertEquals("1000.00", asset.balance.amount)
        screenshot("asset-half-owned")
    }

    private fun serverAccount(name: String) = runBlocking {
        ArgusAccountsApi(requireNotNull(application.authEnvironment).apiBaseUrl, session)
            .list(session.state.value.ownershipEpoch).single { it.nickname == name }
    }
    private fun input(tag: String, value: String) {
        compose.onNodeWithTag(tag).performScrollTo().performClick().performTextReplacement(value)
    }
    private fun click(tag: String) {
        compose.onNodeWithTag(tag).performScrollTo().performClick()
    }
    private fun waitFor(tag: String) {
        compose.waitUntil(30_000) {
            compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() &&
                compose.onAllNodesWithTag("accounts_loading").fetchSemanticsNodes().isEmpty()
        }
        compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed()
    }
    private fun screenshot(stage: String) {
        compose.waitForIdle()
        device.waitForIdle()
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val output = File(context.getExternalFilesDir("evidence"), "accounts-${device.displayWidth}x${device.displayHeight}")
        assertTrue(output.isDirectory || output.mkdirs())
        val language = session.state.value.profile?.language ?: "en"
        val theme = args.getString("accountsTheme") ?: "system"
        assertTrue(device.takeScreenshot(File(output, "$language-$theme-$stage.png")))
    }
}
