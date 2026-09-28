package ai.argus.foundation.auth

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.AtomicFile
import io.github.jan.supabase.auth.user.UserSession
import java.io.File
import java.security.KeyStore
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put

/** Auth-only, device-bound storage. No profile, password, plaintext preference, or backup file. */
internal class EncryptedSessionVault(
    context: Context,
    private val dispatcher: CoroutineDispatcher = Dispatchers.IO,
) : SessionVault {
    private val applicationContext = context.applicationContext
    private val file by lazy { AtomicFile(File(applicationContext.noBackupFilesDir, "argus-session-v1.enc")) }
    private val alias = "argus-session-v1"

    override suspend fun load(): StoredSession? = storage {
        if (!file.baseFile.exists()) return@storage null
        if (file.baseFile.length() > 1_048_576) throw SessionFailure(SessionProblem.STORAGE)
        val bytes = file.openRead().use { stream ->
            val value = stream.readBytes()
            if (value.size > 1_048_576) throw SessionFailure(SessionProblem.STORAGE)
            value
        }
        val plain = SessionEnvelope.open(bytes, key(create = false))
        try {
            val json = sessionJson.parseToJsonElement(plain.toString(Charsets.UTF_8)).jsonObject
            val session = sessionJson.decodeFromJsonElement(UserSession.serializer(), json.getValue("session"))
            val id = requireNotNull(json.string("identity_id"))
            require(id.isNotBlank() && session.user?.id == id)
            require(session.accessToken.isNotBlank() && session.refreshToken.isNotBlank())
            StoredSession(session, id, AccountKind.valueOf(requireNotNull(json.string("kind"))),
                Revocation.valueOf(requireNotNull(json.string("revocation"))))
        } finally {
            plain.fill(0)
        }
    }

    override suspend fun save(value: StoredSession) = storage {
        val plain = buildJsonObject {
            put("session", sessionJson.encodeToJsonElement(UserSession.serializer(), value.session))
            put("identity_id", value.identityId)
            put("kind", value.kind.name)
            put("revocation", value.revocation.name)
        }.toString().toByteArray(Charsets.UTF_8)
        try {
            val encrypted = SessionEnvelope.seal(plain, key(create = true))
            val output = file.startWrite()
            try {
                output.write(encrypted)
                file.finishWrite(output)
            } catch (error: Exception) {
                file.failWrite(output)
                throw error
            }
        } finally {
            plain.fill(0)
        }
    }

    override suspend fun clear() = storage {
        file.delete()
        if (file.baseFile.exists()) throw SessionFailure(SessionProblem.STORAGE)
    }

    private fun key(create: Boolean): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        if (!create) throw SessionFailure(SessionProblem.STORAGE)
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build())
        }.generateKey()
    }

    private suspend fun <T> storage(block: () -> T): T = withContext(dispatcher) {
        try {
            block()
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            // Keystore/crypto/parser exceptions are neither log messages nor UI strings.
            throw SessionFailure(SessionProblem.STORAGE)
        }
    }
}
