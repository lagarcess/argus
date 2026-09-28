package ai.argus.foundation.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import ai.argus.foundation.R

@Composable
internal fun ChatPage(
    composer: String, onComposerChange: (String) -> Unit,
    requireRegistration: () -> Unit, onSend: () -> Unit, unavailable: () -> Unit,
) {
    val composerLabel = stringResource(R.string.type_message)
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp)) {
        SampleNotice()
        Column(
            Modifier.fillMaxWidth().heightIn(min = 190.dp).padding(vertical = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Icon(painterResource(R.drawable.argus_mark), null, Modifier.size(46.dp),
                tint = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(20.dp))
            Text(stringResource(R.string.chat_greeting), style = MaterialTheme.typography.headlineMedium)
            Spacer(Modifier.height(10.dp))
            Text(stringResource(R.string.chat_intro), style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onSend,
                modifier = Modifier.heightIn(min = 48.dp)) {
                Text(stringResource(R.string.finance_question))
            }
            OutlinedButton(onClick = requireRegistration,
                modifier = Modifier.heightIn(min = 48.dp).testTag("guest_action_chat")) {
                Text(stringResource(R.string.record_expense))
            }
        }
        Spacer(Modifier.height(12.dp))
        Surface(shape = RoundedCornerShape(24.dp),
            color = MaterialTheme.colorScheme.surfaceContainerHigh) {
            Column {
                TextField(
                    value = composer, onValueChange = onComposerChange,
                    modifier = Modifier.fillMaxWidth().testTag("composer")
                        .semantics { contentDescription = composerLabel },
                    placeholder = { Text(stringResource(R.string.type_message)) },
                    minLines = 2, maxLines = 5,
                    keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                    colors = TextFieldDefaults.colors(
                        focusedContainerColor = Color.Transparent,
                        unfocusedContainerColor = Color.Transparent,
                        focusedIndicatorColor = Color.Transparent,
                        unfocusedIndicatorColor = Color.Transparent,
                    ),
                )
                Row(Modifier.fillMaxWidth().padding(8.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    QuietIcon(ArgusIcons.Add, R.string.add_attachment, unavailable)
                    Spacer(Modifier.weight(1f))
                    QuietIcon(ArgusIcons.Microphone, R.string.voice_input, unavailable)
                    QuietIcon(ArgusIcons.Send, R.string.send_message, onSend)
                }
            }
        }
        Text(stringResource(R.string.composer_notice),
            Modifier.padding(vertical = 10.dp), style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
