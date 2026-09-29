package ai.argus.foundation.auth

import javax.crypto.KeyGenerator
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SessionEnvelopeTest {
    @Test fun encryptedEnvelopeUsesFreshNoncesAndRoundTripsWithoutPlaintextTokens() {
        val key = KeyGenerator.getInstance("AES").apply { init(256) }.generateKey()
        val plain = "synthetic-access-token and synthetic-refresh-token".toByteArray()
        val first = SessionEnvelope.seal(plain, key)
        val second = SessionEnvelope.seal(plain, key)
        assertFalse(first.contentEquals(second))
        assertFalse(first.toString(Charsets.UTF_8).contains("synthetic-access-token"))
        assertArrayEquals(plain, SessionEnvelope.open(first, key))
        assertArrayEquals(plain, SessionEnvelope.open(second, key))
    }

    @Test fun tamperingWrongKeyAndUnknownEnvelopeVersionFailClosed() {
        val generator = KeyGenerator.getInstance("AES").apply { init(256) }
        val key = generator.generateKey()
        val envelope = SessionEnvelope.seal("synthetic-private-session".toByteArray(), key)
        val corrupted = envelope.copyOf().apply { this[lastIndex] = (this[lastIndex].toInt() xor 1).toByte() }
        val unknownVersion = envelope.copyOf().apply { this[0] = 9 }
        assertTrue(runCatching { SessionEnvelope.open(corrupted, key) }.isFailure)
        assertTrue(runCatching { SessionEnvelope.open(unknownVersion, key) }.isFailure)
        assertTrue(runCatching { SessionEnvelope.open(envelope, generator.generateKey()) }.isFailure)
    }
}
