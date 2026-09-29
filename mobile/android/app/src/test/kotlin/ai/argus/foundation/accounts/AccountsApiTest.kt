package ai.argus.foundation.accounts

import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test

class AccountsApiTest {
    @Test fun errorCodesDistinguishSameStatusAndNeverExposeServerDetail() = runBlocking {
        MockWebServer().use { server ->
            server.start()
            val api = ArgusAccountsApi(server.url("/").toString(), FakeRequests())
            listOf(
                Triple(404, "financial_accounts_unavailable", AccountProblem.UNAVAILABLE),
                Triple(404, "financial_account_not_found", AccountProblem.NOT_FOUND),
                Triple(403, "account_conversion_required", AccountProblem.REGISTRATION_REQUIRED),
                Triple(409, "stale_version", AccountProblem.STALE_VERSION),
                Triple(409, "idempotency_conflict", AccountProblem.IDEMPOTENCY_CONFLICT),
                Triple(422, "validation_error", AccountProblem.VALIDATION),
                Triple(422, "amount_precision", AccountProblem.AMOUNT_PRECISION),
            ).forEach { (status, code, expected) ->
                server.enqueue(MockResponse().setResponseCode(status).setBody(
                    """{"code":"$code","detail":"private server data"}"""))
                try { api.list(1); fail("Expected failure") }
                catch (failure: AccountFailure) {
                    assertEquals(expected, failure.problem)
                    assertFalse(failure.message.orEmpty().contains("private"))
                }
            }
        }
    }

    @Test fun immutableCreateAndOpeningSnapshotTravelWithoutNumericCoercion() = runBlocking {
        MockWebServer().use { server ->
            server.start()
            val api = ArgusAccountsApi(server.url("/").toString(), FakeRequests())
            val payload = buildJsonObject { put("amount", "9007199254740.99"); put("type", "checking"); put("currency", "DOP") }
            repeat(2) {
                server.enqueue(MockResponse().setResponseCode(422).setBody("""{"code":"validation_error"}"""))
                try { api.create(1, "immutable-key", payload) } catch (_: AccountFailure) { }
                val request = server.takeRequest()
                assertEquals("POST", request.method)
                assertEquals("/api/v1/financial-accounts", request.path)
                assertEquals("Bearer synthetic-bearer", request.getHeader("Authorization"))
                assertEquals("immutable-key", request.getHeader("Idempotency-Key"))
                assertEquals(payload.toString(), request.body.readUtf8())
            }
            server.enqueue(MockResponse().setResponseCode(409).setBody("""{"code":"stale_version"}"""))
            val body = draftPayload(AccountDraft(mode = DraftMode.OPENING, expectedVersion = 3, amount = "0"), AccountDraft())
            try { api.opening(1, "test-id", body) } catch (_: AccountFailure) { }
            val request = server.takeRequest()
            assertEquals("PUT", request.method)
            assertEquals("/api/v1/financial-accounts/test-id/opening", request.path)
            assertEquals(body.toString(), request.body.readUtf8())
            assertEquals("null", body["expected_revision"].toString())
            assertEquals("3", body["expected_version"].toString())
        }
    }

    @Test fun redirectsAreNotFollowed() = runBlocking {
        MockWebServer().use { server ->
            server.start()
            val api = ArgusAccountsApi(server.url("/").toString(), FakeRequests())
            server.enqueue(MockResponse().setResponseCode(307).addHeader("Location", server.url("/other")))
            try { api.list(1); fail("Expected failure") }
            catch (failure: AccountFailure) { assertEquals(AccountProblem.INVALID_RESPONSE, failure.problem) }
            assertEquals(1, server.requestCount)
        }
    }
}
