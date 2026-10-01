# Cuadrao voice interaction research

2026-09-30 research, implemented as a design preview on 2026-10-01 following checkpoint bd9890c71. Provider integration remains unconnected; see [implementation evidence](evidence/cuadrao-native-design/voice-system/README.md). The founder wants immersive full-screen voice, clearer minimized voice in chat, and consideration of a short spoken message alongside native dictation and live conversation.

## Findings

At the research baseline, expanded voice used a large sheet with a grabber and 32-point corners; its tray appearance was structural. In chat the active voice bar was a separate sibling above the composer, which made their relationship unclear. The voice-system checkpoint corrected both.

Visually reviewed Mobbin flow previews and specific screens:

- [DeepSeek audio input](https://mobbin.com/flows/3dfc5163-3630-4e4c-9243-b2ab6591db3a): labeled hold-to-speak entry, recording feedback, recognition and a red cancel state. [Recording screen](https://mobbin.com/screens/c1dd1733-75df-4719-91fb-54cb511d260d) explicitly says release to send and slide up to cancel. This supports the short spoken-turn pattern; it does not establish tap-for-live and hold-for-message on one unlabeled icon.
- [ChatGPT voice chat](https://mobbin.com/flows/e513c0fe-fd2a-4f92-b7e7-756c9a8e9996): voice and written responses coexist; active voice changes the composer controls. The older four-circle voice flow returned in search is historical, not used as current style authority.
- [Claude push to talk](https://mobbin.com/screens/f191a932-d66b-4694-9996-84691bab8420): an explicit push-to-talk control and explanatory hold/release hint. This is a live voice control reference, not proof of a voice-note storage contract.
- [Grok switch to text](https://mobbin.com/flows/8bef729b-a311-499e-8047-958767616b5f): observed companion flow ends with a call-ended transcript. It is not evidence that switching views preserves a live session. Companion visuals are not a Cuadrao design reference.
- WhatsApp status recording and Yubo chat recording also appeared: visible cancellation and recording indicators. They are secondary references, not the basis for Cuadrao's AI semantics.

Official sources checked:

- [Apple gestures](https://developer.apple.com/design/human-interface-guidelines/gestures/): discoverable, distinguishable gestures, immediate feedback and alternative ways to perform important actions.
- [Apple modality](https://developer.apple.com/design/human-interface-guidelines/modality): full-screen presentation can support immersion; modality needs a clear benefit and an obvious way out.
- [Apple audio messages](https://support.apple.com/guide/iphone/send-and-receive-audio-messages-iph2e42d3117/ios): explicit Audio entry, stop, review, send and cancel, plus a hold shortcut.
- [OpenAI voice](https://help.openai.com/en/articles/20001274-chatgpt-voice): voice works within a chat with text available; dictation is a separate record/edit/send job. The current help page differs from older indexed snippets, so the opened page is the authority.
- [xAI speech to text](https://docs.x.ai/developers/model-capabilities/audio/speech-to-text) and [speech to speech](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech): provider capabilities exist for transcription and live speech. This does not authorize integration or imply they are wired to Argus.

Mobbin screenshots are captured references, not a guarantee of a current app release. Only returned preview images and specific screen images were visually inspected; metadata alone was not used to infer hidden transitions. Four extra signed image URLs could not be opened by the web reader, so no claims depend on their contents.

## Proposed interaction

| Intent | Entry | Result |
| --- | --- | --- |
| Dictate editable text | iPhone keyboard dictation | Editable composer text; user sends normally |
| Send one spoken prompt | Hold waveform; slide up to lock hands-free; accessibility action for direct recording | One bounded message, text response, no continuing live session |
| Talk continuously | Tap waveform | Live conversation, spoken response with text continuity |

Tap/hold is a Cuadrao proposal to prototype and test, not a demonstrated industry standard. A brief first-use hint should explain both actions; the accessibility recording action supports people who cannot hold. The same pointer sequence must never both start live voice and send a recording. During recording, show duration, distinct 'Grabando mensaje' state, release/send guidance, and a red cancel state with words and haptic feedback. A cancelled hold must not fall through into tap-to-start. Permission interruption, app backgrounding and too-short/empty recordings must not send a message. Locking continues the same recording after release; Detener enters review, then Enviar submits. The accessibility action starts this hands-free state directly.

Full voice should fill the display with the sea, without rounded tray edges, grabber or a visible dimmed app behind it. Keep explicit minimize and end distinct. Swiping down within the content minimizes with the same meaning as the minimize button; system-edge gestures retain their meaning. Settings remains a compact sheet above the immersive scene.

In chat, active voice becomes an integrated upper row of the composer: one waveform, a short live/listening/muted state, mute, end and a clear expand affordance. The waveform is a status/expand control during an active conversation; no simultaneous hold-to-record route. On Home/Plan/Search/Profile, reuse its compact form above navigation. Minimize preserves the session, mute stops microphone input, end closes it. Keep the same conversation, draft and selected voice throughout.

Use state-driven motion: expand/collapse should visually connect the sea/waveform to the active row. Do not add a bouncing launch animation. Reduce Motion uses a simple transition. Background/locked-screen behavior is a separate integration requirement, not implied by moving among Cuadrao surfaces.

## Implementation and review boundary

Next design pass can address immersive presentation, integrated voice composer and simulated message-recording states together. It must remain truthful about the unconnected provider. Do not invent recorded audio, transcription success or agent actions. Whether a spoken prompt retains a playable audio message, its transcript, or both requires an explicit storage/privacy contract before delivery work. Voice input must reuse canonical conversation and action ownership, not create a second chat brain.

Validate on the physical phone: people can predict tap versus hold; accidental touch/drag never sends; cancellation never starts live voice; keyboard dismissal restores navigation; minimize/mute/end are distinguishable; entering settings preserves the session; native dictation and live audio ownership do not compete during eventual integration. Compare the tap/hold prototype with separate labeled entry points if discoverability fails.

## Founder screenshot refinement, 2026-10-01

The supplied DeepSeek screenshots show a larger hold target in the empty text area and an explicit hold-to-speak mode after tapping its audio control. Cuadrao borrows the large target and contextual release/cancel guidance. Its waveform tap retains the approved live-conversation meaning; it does not silently switch between two tap meanings. The empty composer says “Escribe o mantén para hablar.” Focused text and written drafts retain native editing and selection. The waveform and empty composer share one gesture component and one short-message state owner.

The native preview uses exclusive UIKit tap/long-press recognizers, window-relative cancellation distance, and an accessibility action. The original + → Mensaje de voz route was removed in the refinement below. Full-screen voice has explicit minimize/end and content swipe-down; the swipe is disabled at accessibility text sizes to preserve scrolling. Minimized voice is one row inside the chat composer. Production microphone capture, transcription, live audio ownership and recorded-message persistence are still delivery work.

## Hands-free refinement, 2026-10-01

Founder approved replacing the upward cancel gesture with WhatsApp-style up-to-lock and left-to-cancel. The submitted WhatsApp screenshot shows the lock above the recording control and cancellation to its left. Related Mobbin references inspected: [WhatsApp recording flow](https://mobbin.com/flows/0aee0851-eb28-49ab-baee-84f2451596a9), [review flow](https://mobbin.com/flows/1caa50ad-16be-4a66-8fdd-f1b7cdc553c7), and [attachment menu](https://mobbin.com/screens/ae24c300-4896-4223-9285-ad0be9cb182d). These references inform the controls; Cuadrao's tap-for-live AI meaning remains its own design choice.

- Hold the empty composer or waveform: begin one message. Release sends the simulated message unless cancellation or locking is active.
- Slide left: red sea and “Suelta para cancelar.” Move back to disarm cancellation.
- Slide up: animated lock progress and one success haptic. “Puedes soltar” confirms that lifting the finger will continue recording. Once locked, dragging cannot accidentally cancel it.
- Locked recording: explicit Cancelar and Detener; Detener opens review with Descartar and Enviar. The VoiceOver custom action “Grabar sin mantener” reaches the same state without a sustained hold.
- The + tray contains Recibo, Foto and Archivo only.
- Navigation is absent during recording but retains its layout space. It returns after stop/cancel. This is a Cuadrao adaptation, not an observed DeepSeek tab-bar transition. Minimized live voice keeps navigation.
- Recording controls render above the shared scroll chrome so the app's edge blur does not blur actions. Large text gets a full-height, scrollable recording layout with vertically arranged controls.

The chat store owns the single recording state read by gestures, overlay and navigation. Pending review survives switching ordinary app surfaces; changing conversation clears it. Temporary-chat exit includes pending voice review in its existing discard confirmation. Backgrounding or interrupted gestures cancel an active recording.

This remains a visual interaction preview: elapsed time and waveform illustrate state, the microphone is off, and no recording, transcription, provider session, playback or send occurs. [Hands-free evidence](evidence/cuadrao-native-design/voice-lock/README.md).
