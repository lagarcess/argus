package ai.argus.nativeauth

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Values encrypted with a non-exportable Android Keystore AES key, stored in a
 * private preferences file. Excluded from backup by the host app's rules, so it
 * matches the iOS AfterFirstUnlockThisDeviceOnly contract. Keystore crypto and
 * the synchronous preference commit run on [io], never on the caller's dispatcher.
 */
class SecureStore(
    context: Context,
    private val name: String,
    private val io: CoroutineDispatcher = Dispatchers.IO,
) {
    private val prefs = context.getSharedPreferences("argus-secure-$name", Context.MODE_PRIVATE)
    private val alias = "argus-native-auth-$name"

    private fun key(): SecretKey {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (keyStore.getEntry(alias, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build()
        )
        return generator.generateKey()
    }

    suspend fun put(key: String, value: String): Unit = withContext(io) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        val sealed = cipher.iv + cipher.doFinal(value.toByteArray())
        prefs.edit().putString(key, Base64.encodeToString(sealed, Base64.NO_WRAP)).commit()
    }

    suspend fun get(key: String): String? = withContext(io) {
        prefs.getString(key, null)?.let { encoded ->
            val sealed = Base64.decode(encoded, Base64.NO_WRAP)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, sealed.copyOfRange(0, 12)))
            String(cipher.doFinal(sealed.copyOfRange(12, sealed.size)))
        }
    }

    suspend fun remove(key: String): Unit = withContext(io) {
        prefs.edit().remove(key).commit()
    }

    suspend fun clear(): Unit = withContext(io) {
        prefs.edit().clear().commit()
    }
}
