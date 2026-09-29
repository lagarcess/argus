package ai.argus.foundation.auth

import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class AuthEnvironmentTest {
    private fun config(api: String = "http://10.0.2.2:59400", recovery: String = "http://10.0.2.2:59405/auth/forgot-password") =
        AuthEnvironment.validated(api, "http://10.0.2.2:59401", "synthetic-public-key", "local-captcha", recovery)

    @Test fun acceptsExplicitLocalEmulatorServices() { assertNotNull(config()) }

    @Test fun rejectsHostedAndAmbiguousDestinations() {
        listOf("https://arguschat.ai:443", "http://10.0.2.2.evil.test:59400", "http://user@10.0.2.2:59400", "http://10.0.2.2:59400?redirect=https://example.com", "not a URL").forEach {
            assertNull(config(api = it))
        }
    }

    @Test fun recoveryMustStartInExistingBrowserFlow() {
        assertNull(config(recovery = "http://10.0.2.2:59405/auth/recovery"))
        assertNull(config(recovery = "http://10.0.2.2:59405/auth/forgot-password#token"))
    }

    @Test fun missingKeyOrCaptchaDisablesAuth() {
        assertNull(AuthEnvironment.validated("http://localhost:59400", "http://localhost:59401", "", "test", "http://localhost:59405/auth/forgot-password"))
    }
}
