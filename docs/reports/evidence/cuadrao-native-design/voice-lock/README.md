# Cuadrao hands-free voice design checkpoint

2026-10-01. Follows `af20e61c1b7a920d9212e81e218c1aa1d80cead6`. Local design work only; microphone/provider integration remains unconnected.

## Interaction

- Hold the empty composer or waveform to rehearse one recorded message. Release submits the preview.
- Slide up to lock: animated lock and haptic, then “Puedes soltar.” Releasing after lock continues recording; it never submits.
- Slide left to arm red cancellation; release cancels. Diagonal movement has one dominant direction and cannot both lock and cancel.
- Locked mode has Cancelar and Detener. Stop opens Descartar/Enviar review. The accessibility custom action “Grabar sin mantener” starts the same state directly.
- The + tray contains only Recibo, Foto, Archivo. Navigation disappears during recording while its layout space remains reserved. It returns after stop/cancel; pending review survives a trip to Profile.
- Recording controls sit above the app's scroll blur. Large text gets full-height scrollable content and vertical actions. Tap-for-live and minimized live navigation retain their existing meaning.

## Verification

- Final native run: `Test-ArgusFoundation-2026.10.01_01-25-36--0500.xcresult`, **3 tests passed, 0 failures**, terminal `TEST SUCCEEDED`. Committed receipt: [verification.txt](verification.txt).
- Verified composer and waveform holds, left cancellation without live-voice fallthrough, typed draft selection, up-lock from both targets, release staying locked, stop/review, cancel, navigation absence/restoration, review persistence across Profile, clean attachments, English and largest accessibility text. English live entry/minimize/end also passed.
- Deterministic `python3 ios/DesignPreviewTests/run_temporary_chat.py` passed Spanish and English: short holds, cancellation/re-entry, diagonal arbitration, sticky lock, release/stop, accessible direct recording, interruptions, live exclusion, conversation cleanup, pending temporary-review discard guard, draft/attachment preservation.
- Initial five-test pass attempt found navigation still exposed despite opacity/accessibility modifiers. Fixed by removing the navigation child while retaining its container height. Visual inspection found blurred actions and large-text crowding; corrected by placing recording at the root overlay and stacking actions at accessibility sizes. Final captures below supersede those attempts.
- Initial run's unchanged voice preference/proposal and keyboard/profile live-continuity journeys passed. A subsequent redundant live-continuity rerun was stopped during repeated animation-idle waits; it is not counted as a completed final run. Final affected recording journeys above completed cleanly.
- Signed physical iPhone build succeeded. Installed `local.cuadrao.design.47R3855RTJ` as **Cuadrao Preview**, receipt sequence **3200**. CoreDevice confirmed successful application launch.
- `git diff --check` passed; local focused review checked gesture exclusivity, retained touch target, shared state, scene cleanup and preview honesty. [source-sha256.txt](source-sha256.txt) identifies the exact source used for final simulator captures and the device build; subsequent checkpoint edits are documentation/evidence only.

## Captures

- [Hold and contextual instructions](hold.png)
- [Left cancellation, red sea](cancel-left.png)
- [Locked, Spanish](locked-es.png)
- [Locked, English](locked-en.png)
- [Largest accessibility text](locked-large-text.png): actions fit, extra content scrolls.
- [Attachments only](attachments.png)
- [Review preserved after Profile](review-preserved.png)

Held/cancel frames come from the actual final native gesture test, 41.3 and 44.1 seconds into its video. Others are XCTest attachments from the same final run. All listed screenshots were visually inspected. No manual VoiceOver interaction or physical-touch assessment is claimed.

## Limits

No microphone input, transcription, recorded audio, playback, provider session or send occurs. The sea and elapsed time illustrate recording state. Review says no audio was recorded. Real audio retention, permissions, interruptions, latency and agent actions remain delivery work. Physical installation and launch are separate from the founder's touch assessment.

[Research and source references](../../../cuadrao-voice-interaction-research.md)
