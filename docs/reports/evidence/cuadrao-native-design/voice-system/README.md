# Cuadrao voice system design checkpoint

2026-10-01. Local design preview, following `bd9890c71`. No backend/provider or financial-action integration.

## Delivered interaction

- Tap the waveform: immersive full-screen live-voice preview. Swipe down inside the scene or tap minimize to continue elsewhere. Mute and end retain separate meanings.
- In chat, minimized voice is a single row inside the composer, with status, expand, mute and end. Other surfaces retain the compact voice bar.
- Hold the empty, unfocused composer or waveform: short-message preview with green sea, release guidance, slide-up red cancellation and threshold haptics. The gesture cannot fall through into live voice. Written drafts retain native selection.
- The visible `+ → Mensaje de voz` option and accessibility action support start/stop/review/send without a sustained hold. A pending review cannot be overwritten by another recording.
- Spanish first, English parity. Shared selected voice and bundled sample playback are preserved. Native iPhone dictation remains in the keyboard.

## Verification

All five native UI journeys passed on the assigned simulator `8AFB6084-8918-416E-9164-E21061306BEC`: explicit message alternative; composer/waveform hold, cancellation and text selection; voice choice and proposal handoff; voice continuity across keyboard/profile/navigation; English and accessibility-size full voice.

- Initial four-journey run: `Test-ArgusFoundation-2026.10.01_00-37-31--0500.xcresult`, four passed.
- English/large text plus gesture run: `Test-ArgusFoundation-2026.10.01_00-40-13--0500.xcresult`, two passed.
- After recording-only visual corrections, the affected gesture journey passed again: `Test-ArgusFoundation-2026.10.01_00-44-42--0500.xcresult`.
- `python3 ios/DesignPreviewTests/run_temporary_chat.py`: passed both locales, including short hold, cancellation/re-entry, interruption, explicit review, draft/attachment preservation and exclusion during live voice.
- Physical iPhone build succeeded. Installed `local.cuadrao.design.47R3855RTJ` as **Cuadrao Preview**, installation receipt sequence **3192**, and CoreDevice confirmed successful launch.
- `git diff --check`: passed. Local self-review of the changed state, gesture and presentation owners completed.

The screenshots are committed evidence, not just paths to temporary files. `hold-to-speak.png` and `cancel-armed.png` are frames from the final actual gesture test. Full-screen, integrated composer, picker and review screenshots remain representative after the last correction: that delta only changes the held-message overlay. English and accessibility text screenshots were inspected. This run does not claim dark appearance or VoiceOver interaction was manually exercised.

## Honest limits

The microphone is off. Short-message submission rehearses the interaction and explicitly records/sends no audio; it does not invent a transcript or response. The live session, sea and proposal are presentation previews. Voice samples are bundled real audio. Actual recognition, interruption latency, lock-screen audio, permission handling, audio retention and agent actions require the delivery lane. Physical installation and launch are verified; the founder's physical-touch assessment remains open.

## Captures

- [Immersive voice, Spanish](immersive-es.png)
- [Integrated composer, Spanish](compact-es.png)
- [Integrated composer, English](compact-en.png)
- [Hold to speak](hold-to-speak.png)
- [Cancel armed](cancel-armed.png)
- [Accessible message review](message-review.png)
- [Shared voice picker](voice-picker.png)
- [Full voice at accessibility text size](large-text.png)

Research and source links: [voice interaction research](../../../cuadrao-voice-interaction-research.md).
