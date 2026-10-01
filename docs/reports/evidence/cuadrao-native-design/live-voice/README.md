# Live voice design preview

Founder direction, September 30, 2026: focus on a live, agentic conversation.
Remove the redundant composer dictation microphone; native keyboard dictation
remains available according to device configuration. This checkpoint designs the
session presentation only. It does not implement xAI integration or agent actions.

## Reference inspection

- Founder-provided DeepSeek captures: flowing lower-screen color, waveform,
  cancellation feedback. Adapt the flowing background to a live session rather
  than carrying over hold/release sending or swipe-to-cancel gestures.
- [ChatGPT integrated voice](https://mobbin.com/screens/75114316-d81d-4e76-aac3-fd3f896e2865)
  and [empty voice state](https://mobbin.com/screens/cd8f86f0-7117-4961-913e-fd6422ff6a4c):
  inspected visible microphone, end control and text input in the same conversation.
- [Grok companion voice](https://mobbin.com/flows/e2d268cf-49f7-4487-8e7b-b0aa9076cb92):
  inspected voice-to-text entry and microphone affordances. Character presentation,
  camera and companion-specific controls are not appropriate to this scope.
- The Mobbin ChatGPT “Asking ChatGPT (voice)” result showed dictation rather than
  the required live session, so it was not used as the live-call reference.

## Implemented for review

- Empty composer has one waveform control, “Hablar con Cuadrao.” Content changes
  it to Send. Removed the separate dictation button and obsolete preview sheets.
- Full call view: green lower-screen flowing gradients, illustrated waveform,
  status, mute, keyboard and explicit red end control. No slide-to-cancel gesture
  is transplanted onto an open microphone session.
- A visible “Vista previa · El micrófono está apagado” caption marks this local
  presentation. The ellipsis menu explicitly selects listening/speaking examples;
  no timer fakes a connection, answer or elapsed call duration.
- Speaking can be interrupted. Muting input does not implicitly stop the speaking
  state. The quiet muted-listening state stops the decorative motion.
- Minimize leaves a compact voice bar above app navigation; in chat it sits above
  the composer to avoid covering input controls. Keyboard handoff
  returns to the same chat without ending the session or clearing its draft.
- Ending voice preserves the chat and temporary-mode choice. Changing the actual
  chat, entering temporary mode or leaving temporary mode ends the old voice
  preview so it cannot silently attach to another conversation.
- The existing chat store owns one observable voice presentation. No microphone
  capture, audio playback, provider requests, financial writes or permissions.
- Spanish first and English parity. Reduced Motion uses a static sea/waveform;
  scene inactivity pauses the illustration. Controls retain text/accessibility
  labels so color and motion are not the only status cues.

## Verification and pending acceptance

`python3 ios/DesignPreviewTests/run_temporary_chat.py` passes against the actual
native models in Spanish and English. Includes voice start/end, mute while
speaking, interruption, minimize/reopen, keyboard-state draft/attachment
preservation and conversation/temporary boundaries, plus prior temporary checks.

The signed iPhone build passed before the final compact-bar layout correction.
The final simulator build and local Spanish/English model checks passed after that
correction. No new simulator or build cache was created; no iPhone installation
was performed for this checkpoint.

The founder released design simulator `8AFB6084-8918-416E-9164-E21061306BEC`
after #760 moved to Compact `1A90F684-345F-465C-AA50-6A5298F34156`.
Repeated native checks on the design device:

- Spanish voice entry, mute, speaking example while muted, interrupt, keyboard
  handoff, return to full view, minimize, Home continuity and end back to the
  existing conversation.
- Visual review caught the initial compact bar covering composer controls.
  Moved that bar into the chat layout and rechecked the unobstructed controls.
- Temporary entry ends the old voice session; default context is off. Original
  dashed and new-chat icons render. Sending an example locks context.
- Dismissing the new-chat exit confirmation preserves the temporary conversation.
  Temporary content is absent from recent chats; opening an existing chat requires
  confirmation, then returns to that selected regular conversation.
- Model checks additionally cover draft/attachment restoration, whitespace,
  temporary history isolation, voice/chat boundaries and English parity.

Captured against this checkpoint's runtime source (no runtime edits after capture):
[listening](listening.jpg), [typing handoff](typing.jpg),
[compact bar on Home](home.jpg), [temporary icons](temporary.jpg),
[temporary exit guard](exit.jpg).
The simulator used a hardware keyboard; software-keyboard geometry and native
dictation availability are not certified by these images. Automation sometimes
returned before the UI settled; results above were verified with fresh snapshots
and screenshots rather than tool success alone.

Remaining acceptance: physical-iPhone review of this revision, English visual
review, small-screen/Dynamic Type, dark mode, Reduced Motion and VoiceOver.
No real voice/provider behavior is claimed.

Before provider delivery: permissions/consent, actual audio levels, connection and
interruption recovery, background/privacy behavior, same runtime owner, editable
financial proposals and confirmation, retention and provider handling. These
remain with the voice/runtime delivery contract, not this view implementation.

## Follow-up: escape typing and restore the selected share icon

The founder found that focusing the composer hid navigation without a clear way
back. Chat now exposes an accessible keyboard-down control in the header while
typing. Dismissing it restores navigation and compacts the voice presentation
without clearing the draft or ending the call. Minimizing/reopening the full
voice surface also clears typing focus. The control lives in the header because
a simulator autocorrect popup could cover a composer-adjacent button.

The share control now uses the exact horizontal chain-link paths from
`inheritedIcons.link`, reaffirmed by the founder's screenshot. The similarly
named three-node `share` artwork was rejected and is not the final asset.

Final simulator build passed. Reproduced and verified in Spanish on the reserved
design simulator: open voice, choose typing, enter “Mi borrador,” dismiss typing
from the header, visit Home, return to chat. Navigation, draft and active voice
bar remain present. The final chain-link icon was visually inspected.
[Typing escape](typing-dismiss-header.jpg) and
[restored navigation and share icon](navigation-restored.jpg) capture this revision.
English labels are provided; physical keyboard geometry/device checks remain
subject to the earlier acceptance limits.
