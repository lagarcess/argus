package ai.argus.foundation.auth

import kotlinx.coroutines.flow.StateFlow

/** Internal transport seam. Bearers never become application state or a UI argument. */
internal interface AuthenticatedRequests {
    val state: StateFlow<SessionUiState>
    suspend fun <T> authenticatedRequest(ownershipEpoch: Long, request: suspend (String) -> T): T
}

internal class BearerRejected : Exception("Bearer rejected")
internal class SessionAccessFailure : Exception("Session access unavailable")
