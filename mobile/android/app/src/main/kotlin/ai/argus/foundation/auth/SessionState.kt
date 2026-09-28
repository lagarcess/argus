package ai.argus.foundation.auth

/** Only the bearer-bound Argus /me response can populate this projection. */
data class SessionProfile(
    val id: String,
    val email: String?,
    val displayName: String?,
    val language: String?,
    val locale: String?,
)

enum class SessionStatus {
    DISABLED, SIGNED_OUT, WORKING, SIGNED_IN, GUEST_PRESERVED,
    RECOVERY_REQUIRED, REVOCATION_FAILED,
}

enum class SessionProblem {
    INVALID_CREDENTIALS, REJECTED_SESSION, NETWORK, VERIFICATION_UNAVAILABLE,
    INVALID_RESPONSE, STORAGE, REVOCATION, UNSUPPORTED_GUEST,
}

data class SessionUiState(
    val status: SessionStatus,
    val profile: SessionProfile? = null,
    val problem: SessionProblem? = null,
    val ownershipEpoch: Long = 0,
)

/** Never retain a provider exception or its possibly secret-bearing message. */
internal class SessionFailure(val problem: SessionProblem) : Exception(problem.name)
