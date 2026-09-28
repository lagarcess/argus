package ai.argus.foundation

import android.content.Context
import androidx.core.content.edit
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

enum class Appearance {
    SYSTEM, LIGHT, DARK;

    fun isDark(systemDark: Boolean): Boolean = when (this) {
        SYSTEM -> systemDark
        LIGHT -> false
        DARK -> true
    }

    companion object {
        fun fromStored(value: String?): Appearance = entries.firstOrNull { it.name == value } ?: SYSTEM
    }
}

/** Only an app appearance preference is durable; this store holds no product data. */
class AppearanceStore(context: Context) {
    private val preferences = context.getSharedPreferences("appearance", Context.MODE_PRIVATE)
    var selected by mutableStateOf(Appearance.fromStored(preferences.getString("mode", null)))
        private set

    fun select(appearance: Appearance) {
        preferences.edit { putString("mode", appearance.name) }
        selected = appearance
    }
}
