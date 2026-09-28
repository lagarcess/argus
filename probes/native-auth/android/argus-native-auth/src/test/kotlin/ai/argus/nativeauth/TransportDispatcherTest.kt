package ai.argus.nativeauth

import java.util.concurrent.Executors
import kotlin.coroutines.CoroutineContext
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

/** Records the thread each dispatched block runs on. */
private class RecordingDispatcher(name: String) : CoroutineDispatcher() {
    private val executor = Executors.newSingleThreadExecutor { Thread(it, name) }
    private val delegate = executor.asCoroutineDispatcher()
    val threads = mutableListOf<String>()

    override fun dispatch(context: CoroutineContext, block: Runnable) =
        delegate.dispatch(context, Runnable {
            synchronized(threads) { threads += Thread.currentThread().name }
            block.run()
        })

    fun close() = executor.shutdown()
}

class TransportDispatcherTest {
    @Test
    fun theRequestRunsOnTheIoDispatcherNotTheCallersThread() = runBlocking {
        val server = MockWebServer().apply { enqueue(MockResponse().setResponseCode(401).setBody("""{"code":"unauthorized"}""")) }
        val io = RecordingDispatcher("argus-io")
        val caller = Executors.newSingleThreadExecutor { Thread(it, "ui-like-caller") }.asCoroutineDispatcher()
        try {
            server.start()
            val transport = BearerTransport(server.url("/").toString().trimEnd('/'), io = io)
            val (response, callerThread) = withContext(caller) {
                transport.send("GET", "/me") to Thread.currentThread().name
            }
            assertEquals(401, response.status)
            assertEquals("unauthorized", response.problemCode)
            assertEquals("ui-like-caller", callerThread)
            assertEquals(listOf("argus-io"), io.threads.distinct())
            assertNotEquals(callerThread, io.threads.first())
        } finally {
            server.shutdown()
            io.close()
            caller.close()
        }
    }
}
