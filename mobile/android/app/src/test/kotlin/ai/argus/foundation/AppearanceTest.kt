package ai.argus.foundation

import org.junit.Assert.assertEquals
import org.junit.Test

class AppearanceTest {
    @Test
    fun savedChoicesRoundTrip() {
        Appearance.entries.forEach { appearance ->
            assertEquals(appearance, Appearance.fromStored(appearance.name))
        }
    }

    @Test
    fun missingOrUnrecognizedPreferencesFollowTheSystem() {
        listOf(null, "", "UNKNOWN", "light", " DARK ").forEach { stored ->
            assertEquals("Stored value: $stored", Appearance.SYSTEM, Appearance.fromStored(stored))
        }
    }

    @Test
    fun explicitChoicesOverrideTheSystemAndSystemChoiceFollowsIt() {
        val expectations = listOf(
            Triple(Appearance.SYSTEM, false, false),
            Triple(Appearance.SYSTEM, true, true),
            Triple(Appearance.LIGHT, false, false),
            Triple(Appearance.LIGHT, true, false),
            Triple(Appearance.DARK, false, true),
            Triple(Appearance.DARK, true, true),
        )
        expectations.forEach { (appearance, systemDark, expected) ->
            assertEquals("$appearance with systemDark=$systemDark", expected, appearance.isDark(systemDark))
        }
    }
}
