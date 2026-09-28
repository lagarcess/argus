package ai.argus.nativeauth

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.json.JsonObject

class StaleAccountException : Exception("response belongs to a previous account")

/** A response delivered after sign-out or account switch is dropped, not rendered. */
class AccountBoundary {
    private val mutex = Mutex()
    private var epoch = 0
    private val cache = mutableMapOf<String, JsonObject>()

    suspend fun begin(): Int = mutex.withLock { epoch }

    suspend fun end() = mutex.withLock {
        epoch += 1
        cache.clear()
    }

    suspend fun deliver(response: ApiResponse, started: Int, cacheKey: String?): ApiResponse = mutex.withLock {
        if (started != epoch) throw StaleAccountException()
        cacheKey?.let { cache[it] = response.body }
        response
    }

    suspend fun cached(key: String): JsonObject? = mutex.withLock { cache[key] }
}
