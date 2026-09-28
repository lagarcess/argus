@file:OptIn(kotlin.time.ExperimentalTime::class)

package ai.argus.foundation

import ai.argus.foundation.auth.*
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Opt-in, disposable local stack only. Credentials and tokens never enter test output. */
@RunWith(AndroidJUnit4::class)
class SessionDeviceContractTest {
    @Test fun registeredSessionSurvivesExpiryAndRevokesAtServer() = runBlocking {
        assumeTrue(BuildConfig.LOCAL_AUTH_ENABLED)
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.containsKey("email") && args.containsKey("password"))
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val application = context.applicationContext as ArgusApplication
        val controller = requireNotNull(application.sessionController)
        val config = requireNotNull(application.authEnvironment)
        withTimeout(30_000) { while (controller.state.value.status == SessionStatus.WORKING) delay(50) }
        assertEquals(SessionStatus.SIGNED_OUT, controller.state.value.status)
        controller.signIn(requireNotNull(args.getString("email")), requireNotNull(args.getString("password")))
        assertEquals("Sign-in problem: ${controller.state.value.problem}", SessionStatus.SIGNED_IN, controller.state.value.status)
        val owner = requireNotNull(controller.state.value.profile).id
        val vault = EncryptedSessionVault(context)
        val first = requireNotNull(vault.load())
        assertEquals(owner, first.session.user?.id)
        assertNull("Provider email must remain memory-only", first.session.user?.email)
        assertNull("Provider user metadata must remain memory-only", first.session.user?.userMetadata)
        assertNull("Provider app metadata must remain memory-only", first.session.user?.appMetadata)
        assertNull("Unused provider credentials must not be persisted", first.session.providerToken)
        assertNull(first.session.providerRefreshToken)
        val disk = File(context.noBackupFilesDir, "argus-session-v1.enc").readBytes().toString(Charsets.ISO_8859_1)
        assertFalse("Access credential must not be plaintext on disk", disk.contains(first.session.accessToken))
        assertFalse("Refresh credential must not be plaintext on disk", disk.contains(first.session.refreshToken))
        assertFalse("Password must not be persisted", disk.contains(requireNotNull(args.getString("password"))))

        // Stack uses 60-second JWTs; recreate the owner after expiry to force SDK refresh.
        delay(65_000)
        val relaunched = createSessionController(context, config)
        relaunched.restore()
        assertEquals(SessionStatus.SIGNED_IN, relaunched.state.value.status)
        assertEquals(owner, relaunched.state.value.profile?.id)
        val refreshed = requireNotNull(vault.load())
        assertTrue("Expired access credential must be renewed", first.session.accessToken != refreshed.session.accessToken)
        assertTrue("Refresh credential must rotate", first.session.refreshToken != refreshed.session.refreshToken)
        relaunched.signOut()
        assertEquals(SessionStatus.SIGNED_OUT, relaunched.state.value.status)
        assertNull(vault.load())
        assertNull(relaunched.state.value.profile)
        try {
            ArgusSessionBackend(config.apiBaseUrl, config.captchaToken).me(refreshed.session.accessToken)
            fail("Revoked bearer was accepted by Argus")
        } catch (failure: SessionFailure) {
            assertEquals(SessionProblem.REJECTED_SESSION, failure.problem)
        }
        val afterLogout = createSessionController(context, config)
        afterLogout.restore()
        assertEquals(SessionStatus.SIGNED_OUT, afterLogout.state.value.status)
    }

    /** Run in two separate instrumentation processes, with host force-stop between phases. */
    @Test fun processRestartCheckpoint() = runBlocking {
        assumeTrue(BuildConfig.LOCAL_AUTH_ENABLED)
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("checkpoint") in setOf("save", "restore"))
        val application = InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as ArgusApplication
        val controller = requireNotNull(application.sessionController)
        withTimeout(30_000) { while (controller.state.value.status == SessionStatus.WORKING) delay(50) }
        if (args.getString("checkpoint") == "save") {
            assertEquals(SessionStatus.SIGNED_OUT, controller.state.value.status)
            controller.signIn(requireNotNull(args.getString("email")), requireNotNull(args.getString("password")))
        }
        assertEquals(SessionStatus.SIGNED_IN, controller.state.value.status)
        assertEquals(args.getString("email"), controller.state.value.profile?.email)
        if (args.getString("checkpoint") == "restore") {
            controller.signOut()
            assertEquals(SessionStatus.SIGNED_OUT, controller.state.value.status)
        }
    }
}
