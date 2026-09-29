@file:OptIn(kotlin.time.ExperimentalTime::class)

package ai.argus.foundation.auth

import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicBoolean
import java.util.Base64
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.time.Clock
import kotlin.time.Duration.Companion.seconds
import kotlin.time.Instant

/** One serialized mutation owner; the epoch retires private UI before waiting for network work. */
class SessionController internal constructor(
    private val backend: SessionBackend,
    private val vault: SessionVault,
    private val sdk: SessionSdk,
    private val dispatcher: CoroutineDispatcher = Dispatchers.IO,
    private val now: () -> Instant = { Clock.System.now() },
) : AuthenticatedRequests {
    private val mutableState = MutableStateFlow(SessionUiState(SessionStatus.WORKING))
    override val state: StateFlow<SessionUiState> = mutableState.asStateFlow()
    private val mutex = Mutex()
    private val epoch = AtomicLong()
    private val revision = AtomicLong()
    private val restoring = AtomicBoolean()
    private var loaded = false
    private var stored: StoredSession? = null

    /** A 401 refreshes through this owner, but never silently replays a financial write. */
    override suspend fun <T> authenticatedRequest(
        ownershipEpoch: Long,
        request: suspend (String) -> T,
    ): T {
        var result: Result<T>? = null
        operation(ownershipEpoch) {
            if (state.value.status != SessionStatus.SIGNED_IN) throw SessionAccessFailure()
            var record = stored ?: throw SessionAccessFailure()
            if (record.kind != AccountKind.REGISTERED || record.revocation != Revocation.NONE) {
                throw SessionAccessFailure()
            }
            if (record.session.expiresAt <= now() + 30.seconds) {
                refreshStored()
                verifyStored(ownershipEpoch)
                record = stored ?: throw SessionAccessFailure()
            }
            if (epoch.get() != ownershipEpoch || state.value.status != SessionStatus.SIGNED_IN) {
                throw SessionAccessFailure()
            }
            try {
                result = Result.success(request(record.session.accessToken))
            } catch (_: BearerRejected) {
                publish(ownershipEpoch, SessionUiState(SessionStatus.WORKING))
                refreshStored()
                verifyStored(ownershipEpoch)
                throw SessionAccessFailure()
            }
        }
        if (epoch.get() != ownershipEpoch || state.value.status != SessionStatus.SIGNED_IN) {
            throw SessionAccessFailure()
        }
        return result?.getOrThrow() ?: throw SessionAccessFailure()
    }

    suspend fun restore() {
        if (!restoring.compareAndSet(false, true)) return
        val ticket = epoch.get()
        try {
            operation(ticket) {
                loadOnce()
                verifyStored(ticket)
            }
        } finally {
            restoring.set(false)
        }
    }

    suspend fun signIn(email: String, password: String) {
        if (state.value.status != SessionStatus.SIGNED_OUT) return
        val ticket = epoch.incrementAndGet()
        mutableState.value = SessionUiState(SessionStatus.WORKING, ownershipEpoch = ticket)
        operation(ticket) {
            loadOnce()
            if (stored != null) {
                verifyStored(ticket)
                return@operation
            }
            val result = backend.signIn(email, password)
            // Keep even a late login result available for the already-requested sign-out.
            stored = result
            vault.save(result)
            if (epoch.get() == ticket) verifyStored(ticket)
        }
    }

    suspend fun retry() {
        when (state.value.status) {
            SessionStatus.REVOCATION_FAILED -> signOut()
            SessionStatus.RECOVERY_REQUIRED -> restore()
            else -> Unit // A password is never retained for a retry.
        }
    }

    suspend fun refresh() {
        if (state.value.status != SessionStatus.SIGNED_IN) return
        val ticket = epoch.get()
        val requestedRevision = revision.get()
        operation(ticket) {
            if (requestedRevision != revision.get()) return@operation
            if (stored == null || stored?.kind == AccountKind.GUEST || stored?.revocation != Revocation.NONE) return@operation
            publish(ticket, SessionUiState(SessionStatus.WORKING))
            refreshStored()
            if (epoch.get() == ticket) verifyStored(ticket)
        }
    }

    suspend fun signOut() {
        val ticket = epoch.incrementAndGet()
        mutableState.value = SessionUiState(SessionStatus.WORKING, ownershipEpoch = ticket)
        operation(ticket, signingOut = true) {
            loadOnce()
            var record = stored
            if (record != null) {
                if (preserveGuest(record)) {
                    publish(ticket, SessionUiState(SessionStatus.GUEST_PRESERVED))
                    return@operation
                }
                if (record.revocation != Revocation.CONFIRMED) {
                    val retryingUnconfirmedRevocation = record.revocation == Revocation.PENDING
                    record = record.withRevocation(Revocation.PENDING)
                    stored = record
                    vault.save(record)
                    // A prior logout may have reached the server before its response was lost.
                    // Refresh proves whether that session still exists before retrying revocation.
                    if (retryingUnconfirmedRevocation || record.session.expiresAt <= now() + 30.seconds) {
                        refreshStored()
                        record = requireNotNull(stored)
                    }
                    sdk.revoke(record.session)
                    record = record.withRevocation(Revocation.CONFIRMED)
                    stored = record
                    vault.save(record)
                }
                vault.clear()
                sdk.clear()
                stored = null
                revision.incrementAndGet()
            }
            publish(ticket, SessionUiState(SessionStatus.SIGNED_OUT))
        }
    }

    private suspend fun loadOnce() {
        if (!loaded) {
            stored = vault.load()
            loaded = true
        }
    }

    private suspend fun verifyStored(ticket: Long) {
        var record = stored
        if (record == null) {
            publish(ticket, SessionUiState(SessionStatus.SIGNED_OUT))
            return
        }
        if (record.revocation != Revocation.NONE) {
            publish(ticket, SessionUiState(SessionStatus.REVOCATION_FAILED, problem = SessionProblem.REVOCATION))
            return
        }
        if (preserveGuest(record)) {
            publish(ticket, SessionUiState(SessionStatus.GUEST_PRESERVED))
            return
        }
        publish(ticket, SessionUiState(SessionStatus.WORKING))
        if (record.session.expiresAt <= now() + 30.seconds) {
            refreshStored()
            record = requireNotNull(stored)
        }
        val account = backend.me(record.session.accessToken)
        if (account.profile.id != record.identityId) throw SessionFailure(SessionProblem.INVALID_RESPONSE)
        if (epoch.get() != ticket) return
        record = record.withKind(account.kind)
        stored = record
        vault.save(record)
        if (account.kind == AccountKind.GUEST) {
            sdk.clear()
            publish(ticket, SessionUiState(SessionStatus.GUEST_PRESERVED))
        } else {
            sdk.importSession(record.session)
            publish(ticket, SessionUiState(SessionStatus.SIGNED_IN, account.profile))
        }
    }

    private suspend fun refreshStored() {
        val record = requireNotNull(stored)
        try {
            val refreshed = sdk.refresh(record.session)
            if (refreshed.user?.id != record.identityId) throw SessionFailure(SessionProblem.INVALID_RESPONSE)
            // A rotated refresh token must become the recoverable token before another request.
            stored = record.withSession(refreshed)
            vault.save(requireNotNull(stored))
            sdk.importSession(refreshed)
        } finally {
            revision.incrementAndGet()
        }
    }

    private fun preserveGuest(record: StoredSession): Boolean {
        if (record.kind == AccountKind.GUEST) return true
        // SDK 3.2.6 UserInfo omits is_anonymous. This unsigned hint may only deny mutation;
        // it never grants identity, permissions, or profile access (those require /me).
        return runCatching {
            val payload = record.session.accessToken.split('.')[1]
            val json = sessionJson.parseToJsonElement(String(Base64.getUrlDecoder().decode(payload), Charsets.UTF_8)).jsonObject
            json["is_anonymous"]?.jsonPrimitive?.booleanOrNull == true
        }.getOrDefault(false)
    }

    private suspend fun operation(ticket: Long, signingOut: Boolean = false, block: suspend () -> Unit) {
        withContext(dispatcher) {
            mutex.withLock {
                if (epoch.get() != ticket) return@withLock
                try {
                    block()
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (failure: SessionFailure) {
                    if (epoch.get() != ticket) return@withLock
                    if (failure.problem == SessionProblem.REJECTED_SESSION) {
                        // During sign-out only a rejected refresh produces this problem;
                        // raw logout 401/403/404 remain visible revocation failures.
                        discardRejected(ticket)
                    } else if (signingOut) {
                        publish(ticket, SessionUiState(SessionStatus.REVOCATION_FAILED, problem = failure.problem))
                    } else {
                        publish(ticket, SessionUiState(
                            if (stored == null && loaded) SessionStatus.SIGNED_OUT else SessionStatus.RECOVERY_REQUIRED,
                            problem = failure.problem,
                        ))
                    }
                }
            }
        }
    }

    private suspend fun discardRejected(ticket: Long) {
        try {
            vault.clear()
            sdk.clear()
            stored = null
            revision.incrementAndGet()
            publish(ticket, SessionUiState(SessionStatus.SIGNED_OUT, problem = SessionProblem.REJECTED_SESSION))
        } catch (failure: SessionFailure) {
            publish(ticket, SessionUiState(SessionStatus.RECOVERY_REQUIRED, problem = failure.problem))
        }
    }

    private fun publish(ticket: Long, value: SessionUiState) {
        if (epoch.get() == ticket) mutableState.value = value.copy(ownershipEpoch = ticket)
    }
}
