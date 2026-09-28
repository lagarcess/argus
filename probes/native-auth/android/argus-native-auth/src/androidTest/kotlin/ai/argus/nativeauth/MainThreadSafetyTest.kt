package ai.argus.nativeauth

import android.os.StrictMode
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

/**
 * UNVERIFIED on the authoring machine. Calls the blocking boundaries from the
 * Android main thread with StrictMode set to crash on network or disk access.
 * Android also throws NetworkOnMainThreadException without StrictMode.
 */
@RunWith(AndroidJUnit4::class)
class MainThreadSafetyTest {
    private val args = InstrumentationRegistry.getArguments()
    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun transportAndSecureStoreAreSafeToCallFromMain() = runBlocking {
        val store = SecureStore(context, "main-thread-safety")
        val transport = BearerTransport(requireNotNull(args.getString("argusApi")))
        val (status, roundTrip) = withContext(Dispatchers.Main) {
            StrictMode.setThreadPolicy(
                StrictMode.ThreadPolicy.Builder().detectNetwork().detectDiskReads().detectDiskWrites()
                    .penaltyDeath().build()
            )
            try {
                store.put("probe", "value")
                transport.send("GET", "/me").status to store.get("probe")
            } finally {
                store.clear()
                StrictMode.setThreadPolicy(StrictMode.ThreadPolicy.LAX)
            }
        }
        assertEquals(401, status)
        assertEquals("value", roundTrip)
    }
}
