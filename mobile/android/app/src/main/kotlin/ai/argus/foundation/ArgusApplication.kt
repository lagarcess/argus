package ai.argus.foundation

import android.app.Application
import ai.argus.foundation.auth.AuthEnvironment
import ai.argus.foundation.auth.SessionController
import ai.argus.foundation.auth.createSessionController
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/** One session owner outlives activity recreation; UI never restores a second copy. */
class ArgusApplication : Application() {
    private val sessionScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    var authEnvironment: AuthEnvironment? = null
        private set
    var sessionController: SessionController? = null
        private set

    override fun onCreate() {
        super.onCreate()
        authEnvironment = AuthEnvironment.fromBuildConfig()
        sessionController = authEnvironment?.let { createSessionController(applicationContext, it) }
        sessionController?.let { controller -> sessionScope.launch { controller.restore() } }
    }

    fun signIn(email: String, password: String) {
        sessionController?.let { controller -> sessionScope.launch { controller.signIn(email, password) } }
    }

    fun signOut() {
        sessionController?.let { controller -> sessionScope.launch { controller.signOut() } }
    }

    fun retrySession() {
        sessionController?.let { controller -> sessionScope.launch { controller.retry() } }
    }

    fun verifySessionOnForeground() {
        sessionController?.let { controller ->
            sessionScope.launch { controller.restore() }
        }
    }
}
