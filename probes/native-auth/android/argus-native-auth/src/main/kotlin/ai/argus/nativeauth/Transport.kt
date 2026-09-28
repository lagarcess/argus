package ai.argus.nativeauth

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

data class ApiResponse(
    val status: Int,
    val body: JsonObject,
    val headers: Map<String, String>,
    val setCookies: List<Cookie>,
) {
    val problemCode: String?
        get() = (body["code"] ?: (body["detail"] as? JsonObject)?.get("code"))?.jsonPrimitive?.content
}

/**
 * Bearer-only HTTP. CookieJar.NO_COOKIES means Argus's sb-* cookies are never
 * stored or replayed, so a request that forgot its bearer is anonymous.
 * The whole exchange, body read included, runs on [io], never on the caller's
 * dispatcher, so calls from Dispatchers.Main cannot block the UI thread.
 */
class BearerTransport(
    private val base: String,
    private val deviceIp: String? = null,
    private val io: CoroutineDispatcher = Dispatchers.IO,
) {
    private val client = OkHttpClient.Builder().cookieJar(CookieJar.NO_COOKIES).build()

    suspend fun send(
        method: String,
        path: String,
        bearer: String? = null,
        json: JsonElement? = null,
        headers: Map<String, String> = emptyMap(),
    ): ApiResponse = withContext(io) {
        val url = "$base/api/v1$path".toHttpUrl()
        val body = json?.toString()?.toRequestBody("application/json".toMediaType())
        val builder = Request.Builder().url(url).method(method, body ?: if (method == "GET") null else "".toRequestBody())
        deviceIp?.let { builder.header("CF-Connecting-IP", it) }
        bearer?.let { builder.header("Authorization", "Bearer $it") }
        headers.forEach { (name, value) -> builder.header(name, value) }
        client.newCall(builder.build()).execute().use { response ->
            val text = response.body?.string().orEmpty()
            val parsed = runCatching { Json.parseToJsonElement(text).jsonObject }.getOrDefault(JsonObject(emptyMap()))
            ApiResponse(
                status = response.code,
                body = parsed,
                headers = response.headers.associate { (k, v) -> k.lowercase() to v },
                setCookies = Cookie.parseAll(url, response.headers),
            )
        }
    }
}
