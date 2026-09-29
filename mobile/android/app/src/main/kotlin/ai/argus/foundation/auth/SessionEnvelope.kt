package ai.argus.foundation.auth

import javax.crypto.Cipher
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Versioned AES-GCM envelope. The key is supplied only by Android Keystore in production. */
internal object SessionEnvelope {
    private val associatedData = "argus-session-v1".toByteArray(Charsets.UTF_8)

    fun seal(plain: ByteArray, key: SecretKey): ByteArray {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key)
        cipher.updateAAD(associatedData)
        return byteArrayOf(1) + cipher.iv + cipher.doFinal(plain)
    }

    fun open(bytes: ByteArray, key: SecretKey): ByteArray {
        require(bytes.size >= 30 && bytes[0] == 1.toByte())
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, bytes.copyOfRange(1, 13)))
        cipher.updateAAD(associatedData)
        return cipher.doFinal(bytes.copyOfRange(13, bytes.size))
    }
}
