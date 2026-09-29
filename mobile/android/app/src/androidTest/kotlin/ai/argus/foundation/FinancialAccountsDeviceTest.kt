package ai.argus.foundation

import ai.argus.foundation.accounts.ArgusAccountsApi
import ai.argus.foundation.accounts.AccountFailure
import ai.argus.foundation.accounts.AccountProblem
import java.io.IOException
import ai.argus.foundation.auth.SessionStatus
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.time.OffsetDateTime
import java.util.UUID
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Disposable local Postgres acceptance. No credentials or response bodies are printed. */
@RunWith(AndroidJUnit4::class)
class FinancialAccountsDeviceTest {
    private val args get() = InstrumentationRegistry.getArguments()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val application get() = context.applicationContext as ArgusApplication
    private val session get() = requireNotNull(application.sessionController)
    private val client = OkHttpClient()
    private val path = "/api/v1/financial-accounts"
    private val asOf = "2026-01-15T09:30:00-04:00"
    private val zone = "America/Santo_Domingo"

    @Test fun durableWorkflowPreservesZeroUnknownPrecisionAndCorrections() = runBlocking {
        signIn()
        val before = listIds()
        val key = UUID.randomUUID().toString()
        val body = createBody(amount = "0.00")
        // Deliver the real write to Postgres, then lose its response at the transport boundary.
        var committedStatus = 0
        val interruptedClient = OkHttpClient.Builder().addInterceptor { chain ->
            chain.proceed(chain.request()).use { committedStatus = it.code }
            throw IOException("Synthetic response loss")
        }.build()
        try {
            ArgusAccountsApi(requireNotNull(application.authEnvironment).apiBaseUrl, session, interruptedClient)
                .create(session.state.value.ownershipEpoch, key, body)
            fail("A lost response must surface as an uncertain write")
        } catch (failure: AccountFailure) {
            assertEquals(AccountProblem.NETWORK, failure.problem)
        }
        assertEquals(201, committedStatus)
        val zero = request("POST", path, body, key).expect(200)
        assertEquals(setOf(zero.text("id")), listIds() - before)
        assertEquals("known", zero.objectAt("balance").text("state"))
        assertEquals(0L, zero.objectAt("balance").long("amount_minor"))
        assertEquals("0.00", zero.objectAt("balance").text("amount"))
        assertProblem(request("POST", path, createBody(amount = "1.00"), key), 409, "idempotency_conflict")

        val unknown = create(createBody())
        assertEquals("unknown", unknown.objectAt("balance").text("state"))
        assertEquals(JsonNull, unknown.objectAt("balance")["amount"])
        assertEquals(JsonNull, unknown["opening"])
        assertEquals(unknown, get(unknown))
        val edited = patch(unknown, buildJsonObject { put("nickname", "Synthetic reserve"); put("type", "savings") })
        assertEquals("Synthetic reserve", edited.text("nickname"))
        assertProblem(request("PATCH", accountPath(unknown), buildJsonObject {
            put("expected_version", unknown.long("version")); put("nickname", "Stale name")
        }), 409, "stale_version")
        val precise = opening(edited, "90071992547409.93")
        assertEquals(9007199254740993L, precise.objectAt("balance").long("amount_minor"))
        assertEquals("90071992547409.93", precise.objectAt("balance").text("amount"))
        val decoded = ArgusAccountsApi(requireNotNull(application.authEnvironment).apiBaseUrl, session)
            .get(session.state.value.ownershipEpoch, precise.text("id"))
        assertEquals(9007199254740993L, decoded.balance.amountMinor)
        assertEquals("90071992547409.93", decoded.balance.amount)
        assertEquals(zone, precise.objectAt("opening").text("time_zone"))
        assertEquals(OffsetDateTime.parse(asOf).toInstant(),
            OffsetDateTime.parse(precise.objectAt("opening").text("as_of")).toInstant())
        val corrected = opening(precise, "42.19", "Correct synthetic opening typo")
        val history = corrected.objectAt("opening")["revisions"]!!.jsonArray
        assertEquals(2, history.size)
        assertEquals("90071992547409.93", history.first().jsonObject.text("amount"))
        assertEquals("42.19", history.last().jsonObject.text("amount"))
        assertEquals("Correct synthetic opening typo", history.last().jsonObject.text("reason"))
        assertProblem(request("PUT", "${accountPath(corrected)}/opening", buildJsonObject {
            put("expected_version", corrected.long("version")); put("expected_revision", 1); put("amount", "2.00")
            put("reason", "Stale correction")
        }), 409, "stale_version")
        val archived = patch(corrected, buildJsonObject { put("archived", true) })
        assertTrue(archived["archived"]!!.jsonPrimitive.boolean)
        assertEquals(corrected["balance"], archived["balance"])
        assertTrue(listIds().contains(archived.text("id")))
        val restored = patch(archived, buildJsonObject { put("archived", false) })
        assertFalse(get(restored)["archived"]!!.jsonPrimitive.boolean)
        assertEquals(corrected["opening"], restored["opening"])
        val debt = create(createBody(type = "credit_card", amount = "18.27"))
        assertEquals(-1827L, debt.objectAt("balance").long("amount_minor"))
        assertEquals("-18.27", debt.objectAt("balance").text("amount"))
        val debtCorrection = opening(debt, "21.46", "Correct synthetic debt")
        assertEquals(-2146L, debtCorrection.objectAt("balance").long("amount_minor"))
        val originalOpening = debtCorrection.objectAt("opening")
        val dated = request("PUT", "${accountPath(debtCorrection)}/opening", buildJsonObject {
            put("expected_version", debtCorrection.long("version"))
            put("expected_revision", originalOpening.long("revision"))
            put("as_of", "2026-01-14T09:30:00-04:00"); put("reason", "Correct synthetic date")
            // Omit the unchanged owner-signed amount; resending it would flip liability meaning.
        }).expect(200)
        assertEquals(-2146L, dated.objectAt("balance").long("amount_minor"))
        assertEquals(originalOpening["time_zone"], dated.objectAt("opening")["time_zone"])
        val renamed = patch(dated, buildJsonObject { put("nickname", "") })
        assertEquals(JsonNull, renamed["nickname"])
        assertEquals(dated["opening"], renamed["opening"])
        val amountOnly = request("PUT", "${accountPath(renamed)}/opening", buildJsonObject {
            put("expected_version", renamed.long("version"))
            put("expected_revision", renamed.objectAt("opening").long("revision"))
            put("amount", "23.45"); put("reason", "Correct only the synthetic amount")
        }).expect(200)
        assertEquals(-2345L, amountOnly.objectAt("balance").long("amount_minor"))
        assertEquals(renamed.objectAt("opening")["as_of"], amountOnly.objectAt("opening")["as_of"])
        assertEquals(renamed.objectAt("opening")["time_zone"], amountOnly.objectAt("opening")["time_zone"])
    }

    @Test fun callerVisibleVersionProtectsOpeningAgainstCurrencyAndNatureChanges() = runBlocking {
        signIn()
        listOf("currency" to "JPY", "type" to "credit_card").forEach { (field, value) ->
            val readByFirstClient = create(createBody())
            val readBySecondClient = get(readByFirstClient)
            val newer = patch(readBySecondClient, buildJsonObject { put(field, value) })
            assertProblem(request("PUT", "${accountPath(readByFirstClient)}/opening", buildJsonObject {
                put("expected_version", readByFirstClient.long("version")); put("expected_revision", JsonNull)
                put("amount", "100"); put("as_of", asOf); put("time_zone", zone)
            }), 409, "stale_version")
            assertEquals(JsonNull, get(newer)["opening"])
            listOf<JsonElement?>(null, JsonPrimitive(0), JsonPrimitive("not-a-version")).forEach { version ->
                val malformed = buildJsonObject {
                    if (version != null) put("expected_version", version)
                    put("expected_revision", JsonNull); put("amount", "100")
                }
                assertProblem(request("PUT", "${accountPath(newer)}/opening", malformed), 422, "validation_error")
            }
            assertEquals(JsonNull, get(newer)["opening"])
        }
    }

    @Test fun serverRejectsOtherOwnerAcrossReadEditAndOpening() = runBlocking {
        assumeTrue(args.containsKey("secondEmail") && args.containsKey("secondPassword"))
        signIn()
        val first = create(createBody(amount = "7.00"))
        val firstOwner = requireNotNull(session.state.value.profile).id
        session.signOut()
        assertEquals(SessionStatus.SIGNED_OUT, session.state.value.status)
        session.signIn(requireNotNull(args.getString("secondEmail")), requireNotNull(args.getString("secondPassword")))
        assertEquals(SessionStatus.SIGNED_IN, session.state.value.status)
        assertNotEquals(firstOwner, session.state.value.profile?.id)
        assertFalse(listIds().contains(first.text("id")))
        assertProblem(request("GET", accountPath(first)), 404, "financial_account_not_found")
        assertProblem(request("PATCH", accountPath(first), buildJsonObject {
            put("expected_version", first.long("version")); put("nickname", "Cross-owner attempt")
        }), 404, "financial_account_not_found")
        assertProblem(request("PUT", "${accountPath(first)}/opening", buildJsonObject {
            put("expected_version", first.long("version")); put("expected_revision", 1)
            put("amount", "1.00"); put("reason", "Cross-owner attempt")
        }), 404, "financial_account_not_found")
        session.signOut()
        signIn()
        assertEquals(first, get(first))
    }

    /** Host restarts the API and force-stops this app between the two instrumentation invocations. */
    @Test fun serverAndApplicationRestartCheckpoint() = runBlocking {
        assumeTrue(BuildConfig.LOCAL_AUTH_ENABLED)
        val phase = args.getString("accountsCheckpoint")
        assumeTrue(phase in setOf("save", "restore"))
        val fixture = context.getSharedPreferences("financial-accounts-test-checkpoint", 0)
        if (phase == "save") {
            signIn()
            val account = opening(create(createBody(amount = "0.00")), "314.15", "Synthetic restart correction")
            // Test fixture only; product persists neither financial account data nor UI drafts.
            assertTrue(fixture.edit().putString("id", account.text("id"))
                .putString("expected", account.toString()).commit())
        } else {
            awaitSession()
            assertEquals(SessionStatus.SIGNED_IN, session.state.value.status)
            val id = requireNotNull(fixture.getString("id", null))
            val expected = Json.parseToJsonElement(requireNotNull(fixture.getString("expected", null))).jsonObject
            assertEquals(expected, request("GET", "$path/$id").expect(200))
            assertTrue(listIds().contains(id))
            assertTrue(fixture.edit().clear().commit())
        }
    }

    private suspend fun signIn() {
        assumeTrue(BuildConfig.LOCAL_AUTH_ENABLED)
        assumeTrue(args.containsKey("email") && args.containsKey("password"))
        awaitSession()
        if (session.state.value.status == SessionStatus.SIGNED_IN) session.signOut()
        assertEquals(SessionStatus.SIGNED_OUT, session.state.value.status)
        session.signIn(requireNotNull(args.getString("email")), requireNotNull(args.getString("password")))
        assertEquals("Session must verify before financial requests", SessionStatus.SIGNED_IN, session.state.value.status)
    }

    private suspend fun awaitSession() = withTimeout(30_000) {
        while (session.state.value.status == SessionStatus.WORKING) delay(50)
    }

    private fun createBody(type: String = "checking", amount: String? = null) = buildJsonObject {
        put("type", type); put("currency", "USD"); put("nickname", "Synthetic account")
        if (amount != null) put("amount", amount)
        put("as_of", asOf); put("time_zone", zone)
    }
    private fun accountPath(account: JsonObject) = "$path/${account.text("id")}"
    private suspend fun create(body: JsonObject) = request("POST", path, body, UUID.randomUUID().toString()).expect(201)
    private suspend fun get(account: JsonObject) = request("GET", accountPath(account)).expect(200)
    private suspend fun listIds() = request("GET", path).expect(200)["accounts"]!!.jsonArray
        .map { it.jsonObject.text("id") }.toSet()
    private suspend fun patch(account: JsonObject, fields: JsonObject) = request("PATCH", accountPath(account),
        JsonObject(fields + ("expected_version" to JsonPrimitive(account.long("version"))))).expect(200)
    private suspend fun opening(account: JsonObject, amount: String, reason: String? = null) = request("PUT",
        "${accountPath(account)}/opening", buildJsonObject {
            put("expected_version", account.long("version"))
            put("expected_revision", account["opening"]?.takeUnless { it is JsonNull }?.jsonObject?.get("revision") ?: JsonNull)
            put("amount", amount); put("as_of", asOf); put("time_zone", zone)
            if (reason != null) put("reason", reason)
        }).expect(200)

    private suspend fun request(method: String, route: String, body: JsonObject? = null, key: String? = null): Reply =
        session.authenticatedRequest(session.state.value.ownershipEpoch) { bearer ->
            val request = Request.Builder().url(requireNotNull(application.authEnvironment).apiBaseUrl.trimEnd('/') + route)
                .header("Authorization", "Bearer $bearer")
                .method(method, body?.toString()?.toRequestBody("application/json".toMediaType()))
            if (key != null) request.header("Idempotency-Key", key)
            client.newCall(request.build()).execute().use { response ->
                Reply(response.code, Json.parseToJsonElement(requireNotNull(response.body).string()).jsonObject)
            }
        }

    private fun assertProblem(reply: Reply, status: Int, code: String) {
        assertEquals("Unexpected problem HTTP status", status, reply.status)
        assertEquals(code, reply.body.text("code"))
    }
    private data class Reply(val status: Int, val body: JsonObject) {
        fun expect(code: Int): JsonObject {
            assertEquals("Unexpected financial HTTP status", code, status)
            return body
        }
    }
    private fun JsonObject.text(key: String) = getValue(key).jsonPrimitive.content
    private fun JsonObject.long(key: String) = getValue(key).jsonPrimitive.long
    private fun JsonObject.objectAt(key: String) = getValue(key).jsonObject
}
