@file:OptIn(kotlin.time.ExperimentalTime::class)

package ai.argus.foundation.auth

import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AuthRequestTest {
    private lateinit var server: MockWebServer
    private lateinit var backend: ArgusSessionBackend

    @Before fun setUp() {
        server = MockWebServer().apply { start() }
        backend = ArgusSessionBackend(server.url("/").toString(), "synthetic-captcha")
    }
    @After fun tearDown() { server.shutdown() }

    @Test fun loginUsesArgusContractAndMeUsesOnlyTheReturnedBearer() = runBlocking {
        val session = testSession().session
        server.enqueue(json(buildJsonObject {
            put("session", buildJsonObject {
                sessionJson.encodeToJsonElement(io.github.jan.supabase.auth.user.UserSession.serializer(), session).jsonObject.forEach { (key, value) -> put(key, value) }
                put("expires_at", session.expiresAt.epochSeconds)
            })
        }.toString()).addHeader("Set-Cookie", "sb-auth-token=must-not-be-reused; Path=/"))
        val signedIn = backend.signIn("person@example.test", "synthetic-password")
        val login = server.takeRequest()
        assertEquals("POST", login.method)
        assertEquals("/api/v1/auth/login", login.path)
        assertNull(login.getHeader("Authorization"))
        val body = sessionJson.parseToJsonElement(login.body.readUtf8()).jsonObject
        assertEquals(setOf("email", "password", "captcha_token"), body.keys)
        assertEquals("person@example.test", body.string("email"))
        assertEquals("synthetic-password", body.string("password"))
        assertEquals("synthetic-captcha", body.string("captcha_token"))

        server.enqueue(json(meResponse()))
        val verified = backend.me(signedIn.session.accessToken)
        val me = server.takeRequest()
        assertEquals("GET", me.method)
        assertEquals("/api/v1/me", me.path)
        assertEquals("Bearer ${session.accessToken}", me.getHeader("Authorization"))
        assertNull(me.getHeader("Cookie"))
        assertEquals("Verified name", verified.profile.displayName)
        assertEquals("es-419", verified.profile.language)
    }

    @Test fun verificationFailuresDistinguishInvalidSessionFromTransientServerState() = runBlocking {
        listOf(401 to SessionProblem.REJECTED_SESSION, 403 to SessionProblem.REJECTED_SESSION,
            429 to SessionProblem.VERIFICATION_UNAVAILABLE, 503 to SessionProblem.VERIFICATION_UNAVAILABLE).forEach { (code, expected) ->
            server.enqueue(json("{\"detail\":\"untrusted secret-bearing provider error\"}").setResponseCode(code))
            assertEquals(expected, failure { backend.me("synthetic-access") }.problem)
        }
    }

    @Test fun actualPythonSessionShapeAcceptsNullableDefaultsAndPreservesServerExpiry() = runBlocking {
        val fixture = requireNotNull(javaClass.getResource("/auth/argus-login-synthetic.json")).readText()
        server.enqueue(json(fixture))
        val record = backend.signIn("synthetic@example.test", "synthetic-password")
        assertEquals("synthetic", record.identityId)
        assertTrue(record.session.user!!.factors.isEmpty())
        assertEquals(1790636756L, record.session.expiresAt.epochSeconds)
        assertEquals(AccountKind.UNKNOWN, record.kind)
    }

    @Test fun defaultCoercionNeverAcceptsNullCredentialsOrMissingServerExpiry() = runBlocking {
        val fixture = sessionJson.parseToJsonElement(requireNotNull(javaClass.getResource("/auth/argus-login-synthetic.json")).readText()).jsonObject
        listOf("access_token", "refresh_token", "expires_at").forEach { field ->
            val invalid = buildJsonObject {
                put("session", buildJsonObject {
                    fixture.getValue("session").jsonObject.forEach { (key, value) ->
                        put(key, if (key == field) kotlinx.serialization.json.JsonNull else value)
                    }
                })
            }
            server.enqueue(json(invalid.toString()))
            assertEquals(SessionProblem.INVALID_RESPONSE, failure { backend.signIn("synthetic@example.test", "synthetic") }.problem)
        }
    }

    @Test fun invalidCredentialsAreDistinctFromServerUnavailable() = runBlocking {
        server.enqueue(json("{}").setResponseCode(401))
        assertEquals(SessionProblem.INVALID_CREDENTIALS, failure { backend.signIn("a@example.test", "synthetic") }.problem)
        server.enqueue(json("{}").setResponseCode(503))
        assertEquals(SessionProblem.VERIFICATION_UNAVAILABLE, failure { backend.signIn("a@example.test", "synthetic") }.problem)
    }

    @Test fun redirectsNeverForwardBearerOrPasswords() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(307).addHeader("Location", server.url("/redirected")))
        assertEquals(SessionProblem.INVALID_RESPONSE, failure { backend.me("synthetic-access") }.problem)
        assertEquals(1, server.requestCount)
    }

    @Test fun malformedOrMissingProfileIdentityDoesNotCreateAPrivateProfile() = runBlocking {
        listOf("not json", "{}", "{\"account_kind\":\"registered\",\"user\":{}}",
            "{\"account_kind\":\"unexpected\",\"user\":{\"id\":\"a\"}}").forEach { body ->
            server.enqueue(json(body))
            assertEquals(SessionProblem.INVALID_RESPONSE, failure { backend.me("synthetic-access") }.problem)
        }
    }

    @Test fun sdkLogoutDoesNotSwallowAnyRejectedResponseOrDeleteVault() = runBlocking {
        val config = AuthEnvironment(server.url("/").toString(), server.url("/").toString(),
            "synthetic-public-key", "synthetic-captcha", server.url("/auth/forgot-password").toString())
        val sdk = createSessionSdk(config)
        val original = testSession()
        val vault = FakeVault(original)
        val controller = SessionController(FakeBackend(), vault, sdk) { testNow }
        controller.restore()
        listOf(401, 403, 404, 503).forEachIndexed { index, code ->
            if (index > 0) server.enqueue(json(sessionJson.encodeToString(io.github.jan.supabase.auth.user.UserSession.serializer(), original.session)))
            server.enqueue(json("{\"msg\":\"synthetic rejection\"}").setResponseCode(code))
            controller.signOut()
            assertEquals(SessionStatus.REVOCATION_FAILED, controller.state.value.status)
            assertNull(controller.state.value.profile)
            assertEquals(original.session.accessToken, vault.value?.session?.accessToken)
            assertEquals(Revocation.PENDING, vault.value?.revocation)
            if (index > 0) assertEquals("/auth/v1/token?grant_type=refresh_token", server.takeRequest().path)
            val request = server.takeRequest()
            assertEquals("POST", request.method)
            assertEquals("/auth/v1/logout?scope=local", request.path)
            assertEquals("Bearer ${original.session.accessToken}", request.getHeader("Authorization"))
            assertEquals("synthetic-public-key", request.getHeader("apikey"))
        }
        server.enqueue(json(sessionJson.encodeToString(io.github.jan.supabase.auth.user.UserSession.serializer(), original.session)))
        server.enqueue(MockResponse().setResponseCode(204))
        controller.retry()
        assertEquals(SessionStatus.SIGNED_OUT, controller.state.value.status)
        assertNull(vault.value)
    }

    @Test fun sdkRefreshUsesTheOfficialRefreshTokenGrant() = runBlocking {
        val config = AuthEnvironment(server.url("/").toString(), server.url("/").toString(),
            "synthetic-public-key", "synthetic-captcha", server.url("/auth/forgot-password").toString())
        val sdk = createSessionSdk(config)
        val original = testSession()
        val next = testSession(token = "next-access").session
        server.enqueue(json(sessionJson.encodeToString(io.github.jan.supabase.auth.user.UserSession.serializer(), next)))
        assertEquals("next-access", sdk.refresh(original.session).accessToken)
        val request = server.takeRequest()
        assertEquals("POST", request.method)
        assertEquals("/auth/v1/token?grant_type=refresh_token", request.path)
        assertEquals(original.session.refreshToken, sessionJson.parseToJsonElement(request.body.readUtf8()).jsonObject.string("refresh_token"))
        assertTrue(request.getHeader("Authorization") != "Bearer ${original.session.accessToken}")
    }

    @Test fun unreachableRevocationRemainsRetryableAndCannotExposeProviderMessages() = runBlocking {
        val config = AuthEnvironment(server.url("/").toString(), server.url("/").toString(),
            "synthetic-public-key", "synthetic-captcha", server.url("/auth/forgot-password").toString())
        val sdk = createSessionSdk(config)
        val vault = FakeVault(testSession())
        val controller = SessionController(FakeBackend(), vault, sdk) { testNow }
        controller.restore()
        server.shutdown()
        controller.signOut()
        assertEquals(SessionStatus.REVOCATION_FAILED, controller.state.value.status)
        assertEquals(SessionProblem.NETWORK, controller.state.value.problem)
        assertEquals(Revocation.PENDING, vault.value?.revocation)
        val error = failure { sdk.revoke(testSession().session) }
        assertEquals("NETWORK", error.message)
        assertNull(error.cause)
    }

    private fun json(body: String) = MockResponse().setHeader("Content-Type", "application/json").setBody(body)
    private fun meResponse() = """{"account_kind":"registered","user":{"id":"account-a","email":"a@example.test","display_name":"Verified name","language":"es-419","locale":"es-DO"},"capabilities":{"ignored":true},"future_field":"ignored"}"""
    private suspend fun failure(block: suspend () -> Unit): SessionFailure {
        try { block() } catch (failure: SessionFailure) { return failure }
        throw AssertionError("Expected a finite session failure")
    }
}
