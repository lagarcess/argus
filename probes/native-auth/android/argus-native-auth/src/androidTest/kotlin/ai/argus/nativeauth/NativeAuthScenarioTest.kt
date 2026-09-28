package ai.argus.nativeauth

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID
import kotlin.time.Duration.Companion.minutes

/**
 * UNVERIFIED on the authoring machine (no Android SDK). Mirrors the Swift
 * I-scenarios. Run: probes/native-auth/android/README.md.
 * Pass anonKey and serviceKey as instrumentation arguments from `supabase status`.
 */
@RunWith(AndroidJUnit4::class)
class NativeAuthScenarioTest {
    private val args = InstrumentationRegistry.getArguments()
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val run = UUID.randomUUID().toString().take(8)
    private val http = OkHttpClient()
    private val captcha = "native-proof-local-captcha"
    private var ipCounter = 0
    private val net = (1..250).random() to (1..250).random()

    private fun arg(name: String) = requireNotNull(args.getString(name)) { "missing instrumentation arg $name" }

    private fun client(name: String, transport: HandoffTransport = HandoffTransport.SCOPED_COOKIES, base: String = arg("argusApi")) =
        ArgusNativeClient(context, arg("supabaseUrl"), arg("anonKey"), base, "$run-$name", transport, "10.${net.first}.${net.second}.${++ipCounter}")

    private fun user(label: String): Pair<String, String> {
        val email = "native-android-$label-$run@proof.argus.local"
        val password = UUID.randomUUID().toString() + "x9"
        val service = arg("serviceKey")
        fun post(url: String, body: String, prefer: String? = null) = Request.Builder().url(url)
            .header("apikey", service).header("Authorization", "Bearer $service")
            .apply { prefer?.let { header("Prefer", it) } }
            .post(body.toRequestBody("application/json".toMediaType())).build()
        http.newCall(post("${arg("supabaseUrl")}/auth/v1/admin/users",
            """{"email":"$email","password":"$password","email_confirm":true}""")).execute().use { assertEquals(200, it.code) }
        http.newCall(post("${arg("supabaseUrl")}/rest/v1/private_alpha_allowlist", """{"email":"$email"}""",
            "resolution=ignore-duplicates")).execute().close()
        return email to password
    }

    private fun result(id: String, scenario: String, ok: Boolean, observed: Map<String, Any?>) {
        println("NATIVE_PROBE_RESULT {\"id\":\"$id\",\"scenario\":\"$scenario\",\"verdict\":\"${if (ok) "pass" else "fail"}\",\"observed\":\"$observed\"}")
        assertTrue("$id $observed", ok)
    }

    @Test fun k1SignInPersistsAcrossRelaunch() = runTest {
        val (email, password) = user("k1")
        client("k1").signIn(email, password, captcha)
        val me = client("k1").request("GET", "/me")
        result("K1", "Keystore-backed session survives a new client instance", me.status == 200, mapOf("me" to me.status))
    }

    @Test fun k3ConcurrentRequestsShareOneRefresh() = runTest(timeout = 3.minutes) {
        val (email, password) = user("k3")
        val c = client("k3")
        c.signIn(email, password, captcha)
        val (decoyEmail, decoyPassword) = user("k3-decoy")
        client("k3-decoy").signIn(decoyEmail, decoyPassword, captcha)
        delay(32_000)
        val statuses = (1..8).map { async { c.request("GET", "/me").status } }.awaitAll()
        result("K3", "Eight concurrent requests inside the refresh margin", statuses.all { it == 200 }, mapOf("statuses" to statuses))
    }

    @Test fun k4RevokedElsewhereSignsOut() = runTest {
        val (email, password) = user("k4")
        val phone = client("k4-phone"); val tablet = client("k4-tablet")
        phone.signIn(email, password, captcha); tablet.signIn(email, password, captcha)
        tablet.supabase.auth.signOut(io.github.jan.supabase.auth.SignOutScope.GLOBAL)
        val outcome = runCatching { phone.request("GET", "/me") }.exceptionOrNull()
        result("K4", "Another device signs out everywhere", outcome is ArgusAuthException.SignedOut, mapOf("outcome" to outcome?.javaClass?.simpleName))
    }

    @Test fun k6AccountSwitchDropsInFlight() = runTest {
        val (a, ap) = user("k6a"); val (b, bp) = user("k6b")
        val c = client("k6")
        c.signIn(a, ap, captcha)
        val started = c.boundary.begin()
        val late = c.transport.send("GET", "/me", c.supabase.auth.currentAccessTokenOrNull())
        c.signOut(); c.signIn(b, bp, captcha)
        val dropped = runCatching { c.boundary.deliver(late, started, "me") }.exceptionOrNull() is StaleAccountException
        val bob = c.request("GET", "/me").body["user"]?.jsonObject?.get("email")?.jsonPrimitive?.content
        result("K6", "Alice's response arrives after switching to Bob", dropped && bob == b, mapOf("dropped" to dropped, "bob" to (bob == b)))
    }

    @Test fun k7GuestConversionScopedCookies() = runTest {
        val (email, password) = user("k7")
        val c = client("k7")
        c.startGuest(captcha)
        val conversation = c.request("POST", "/conversations", buildJsonObject { put("title", JsonNull) })
            .body["conversation"]!!.jsonObject["id"]!!.jsonPrimitive.content
        c.createHandoff(email, conversation)
        assertNotNull(c.handoffs.current)
        val outcome = c.signIn(email, password, captcha)
        val owned = c.request("GET", "/conversations").body["items"]!!.jsonArray.map { it.jsonObject["id"]!!.jsonPrimitive.content }
        assertNull(c.handoffs.current)
        result("K7", "Guest converts with Keystore-held handoff cookies", outcome.claimedConversationId == conversation && conversation in owned,
            mapOf("claimed" to (outcome.claimedConversationId == conversation)))
    }

    @Test fun k8GuestConversionHeaderTransport() = runTest {
        val (email, password) = user("k8")
        val c = client("k8", HandoffTransport.HEADER, arg("adapter"))
        c.startGuest(captcha)
        val conversation = c.request("POST", "/conversations", buildJsonObject { put("title", JsonNull) })
            .body["conversation"]!!.jsonObject["id"]!!.jsonPrimitive.content
        c.createHandoff(email, conversation)
        val outcome = c.signIn(email, password, captcha)
        result("K8", "Guest converts over the synthetic header transport (level 2)", outcome.claimedConversationId == conversation,
            mapOf("claimed" to (outcome.claimedConversationId == conversation)))
    }
}
