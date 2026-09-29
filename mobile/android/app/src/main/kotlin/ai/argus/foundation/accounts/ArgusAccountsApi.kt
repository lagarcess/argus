package ai.argus.foundation.accounts

import ai.argus.foundation.auth.AuthenticatedRequests
import ai.argus.foundation.auth.BearerRejected
import ai.argus.foundation.auth.SessionAccessFailure
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.*
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

internal interface AccountsApi {
    suspend fun list(epoch: Long): List<FinancialAccount>
    suspend fun get(epoch: Long, id: String): FinancialAccount
    suspend fun create(epoch: Long, key: String, payload: JsonObject): FinancialAccount
    suspend fun edit(epoch: Long, id: String, payload: JsonObject): FinancialAccount
    suspend fun opening(epoch: Long, id: String, payload: JsonObject): FinancialAccount
}

internal class ArgusAccountsApi(
    baseUrl: String,
    private val session: AuthenticatedRequests,
    private val client: OkHttpClient = OkHttpClient.Builder()
        .followRedirects(false).followSslRedirects(false).callTimeout(20, TimeUnit.SECONDS).build(),
    private val dispatcher: CoroutineDispatcher = Dispatchers.IO,
) : AccountsApi {
    private val root = baseUrl.trimEnd('/').toHttpUrl().newBuilder()
        .addPathSegments("api/v1/financial-accounts").build()

    override suspend fun list(epoch: Long): List<FinancialAccount> = parse {
        request(epoch, "GET").getValue("accounts").jsonArray.map { decodeAccount(it.jsonObject) }
    }
    override suspend fun get(epoch: Long, id: String) = parse { decodeAccount(request(epoch, "GET", id)) }
    override suspend fun create(epoch: Long, key: String, payload: JsonObject) = parse {
        decodeAccount(request(epoch, "POST", payload = payload, key = key))
    }
    override suspend fun edit(epoch: Long, id: String, payload: JsonObject) = parse {
        decodeAccount(request(epoch, "PATCH", id, payload = payload))
    }
    override suspend fun opening(epoch: Long, id: String, payload: JsonObject) = parse {
        decodeAccount(request(epoch, "PUT", id, opening = true, payload = payload))
    }

    private suspend fun request(
        epoch: Long, method: String, id: String? = null, opening: Boolean = false,
        payload: JsonObject? = null, key: String? = null,
    ): JsonObject = withContext(dispatcher) {
        try {
            session.authenticatedRequest(epoch) { bearer ->
                val url = root.newBuilder().apply {
                    if (id != null) addPathSegment(id)
                    if (opening) addPathSegment("opening")
                }.build()
                val request = Request.Builder().url(url).header("Authorization", "Bearer $bearer")
                    .method(method, payload?.toString()?.toRequestBody("application/json".toMediaType()))
                    .apply { if (key != null) header("Idempotency-Key", key) }.build()
                client.newCall(request).execute().use { response ->
                    if (response.code == 401) throw BearerRejected()
                    val source = response.body?.source() ?: throw AccountFailure(AccountProblem.INVALID_RESPONSE)
                    if (source.request(2_097_153)) throw AccountFailure(AccountProblem.INVALID_RESPONSE)
                    val json = parse { accountsJson.parseToJsonElement(source.readUtf8()).jsonObject }
                    if (!response.isSuccessful) {
                        throw AccountFailure(accountProblem(json["code"]?.jsonPrimitive?.contentOrNull))
                    }
                    json
                }
            }
        } catch (_: IOException) {
            throw AccountFailure(AccountProblem.NETWORK)
        } catch (_: SessionAccessFailure) {
            throw AccountFailure(AccountProblem.AUTH_REQUIRED)
        }
    }

    private inline fun <T> parse(block: () -> T): T = try {
        block()
    } catch (failure: AccountFailure) { throw failure
    } catch (_: IllegalArgumentException) { throw AccountFailure(AccountProblem.INVALID_RESPONSE)
    } catch (_: NoSuchElementException) { throw AccountFailure(AccountProblem.INVALID_RESPONSE) }
}
