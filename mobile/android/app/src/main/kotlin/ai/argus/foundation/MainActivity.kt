package ai.argus.foundation

import android.os.Bundle
import android.content.ActivityNotFoundException
import android.content.Intent
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.net.toUri
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.collectAsState
import ai.argus.foundation.ui.ArgusApp
import ai.argus.foundation.ui.SessionLocale

class MainActivity : ComponentActivity() {
    override fun onStart() {
        super.onStart()
        (application as ArgusApplication).verifySessionOnForeground()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val appearance = AppearanceStore(applicationContext)
        val sessionOwner = application as ArgusApplication
        enableEdgeToEdge()
        setContent {
            val sessionState = sessionOwner.sessionController?.state?.collectAsState()?.value
            val dark = appearance.selected.isDark(isSystemInDarkTheme())
            SideEffect {
                val style = if (dark) SystemBarStyle.dark(android.graphics.Color.TRANSPARENT)
                    else SystemBarStyle.light(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT)
                enableEdgeToEdge(statusBarStyle = style, navigationBarStyle = style)
            }
            SessionLocale(sessionState) { ArgusTheme(dark) {
                ArgusApp(
                    appearance.selected, appearance::select,
                    sessionState = sessionState,
                    accountsController = sessionOwner.accountsController,
                    onSignIn = sessionOwner::signIn,
                    onSignOut = sessionOwner::signOut,
                    onSessionRetry = sessionOwner::retrySession,
                    onRecovery = sessionOwner.authEnvironment?.recoveryUrl?.let { recoveryUrl ->
                        { openRecovery(recoveryUrl) }
                    },
                )
            } }
        }
    }

    private fun openRecovery(recoveryUrl: String) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, recoveryUrl.toUri()))
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(this, R.string.session_browser_unavailable, Toast.LENGTH_LONG).show()
        }
    }
}
