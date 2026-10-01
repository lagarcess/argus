# Voice companion design checkpoint

2026-09-30. Extends scroll-edge checkpoint 8afb0098 in the isolated native design checkout. UI and sample playback only; no microphone capture, provider session, real agent execution or financial persistence.

## Accepted direction implemented

Voice begins inline with the current chat still visible. A compact status bar follows navigation, with mute, voice choice, expand and explicit X/end controls. Starter prompts recede while voice is active. The optional green sea uses a native large sheet; pulling its grabber down minimizes without ending. Profile reserves space for the persistent controls.

Voice choice is shared between the compact/expanded controls and Profile > Preferences > Voice. One AppStorage preference owns selection, independent of response tone/length. The chooser has a cancellable candidate, selected state and real bundled public xAI audio samples for Ara, Eve and Sal. This is a curated design set, not a frozen production roster. English samples are disclosed. Playback stops on selection change, dismissal and app backgrounding. No network or paid synthesis is involved.

Expanded voice > preview menu > Show example proposal moves to Plan with voice still active. The card can be reviewed or dismissed. It labels planned contributions separately from savings, changes no accounts and survives ending voice within the current preview conversation. Switching conversations clears the proposal. This is an illustration, not a new production Plan implementation.

## Research

- [Mobbin ChatGPT choosing a voice](https://mobbin.com/flows/2bb2faff-fdfd-4899-b768-a93a7f97cead): visually inspected compact choice, description, preview and selected-state treatment. Cuadrao uses a small list to compare three voices directly.
- [Mobbin integrated ChatGPT voice](https://mobbin.com/screens/75114316-d81d-4e76-aac3-fd3f896e2865): previously inspected continuity of visible conversation and voice controls.
- [xAI official voices and public samples](https://docs.x.ai/developers/model-capabilities/audio/voice). Asset source records are beside VoiceSamples. Production roster/licensing and provider integration remain delivery work.

## Verification and physical delivery

- Native simulator build succeeded on reserved device 8AFB6084-8918-416E-9164-E21061306BEC.
- Focused XCUITest: testVoiceStaysAvailableAcrossSheetsAndSurfaces passed on final behavioral source (15.774 seconds). Uses the sheet grabber to dismiss, verifies Profile remains reachable with voice active, then explicitly ends voice.
- Focused XCUITest: testVoiceChoiceAndProposalHandoff passed (32.975 seconds): real sample enters playback, selection stops playback, Sal appears in Profile and persists after relaunch, proposal opens in Plan, review completes and remains after voice ends. Exported screenshots are from this successful run.
- Final Spanish/English actual-model checks passed for voice state, interruption, keyboard handoff, temporary boundaries and draft preservation.
- Final physical iPhone build succeeded; existing signing identity and single DerivedData folder reused. Installed and launched bundle local.cuadrao.design.47R3855RTJ on paired iPhone 00008120-001428C90E04201E using devicectl. Device installation receipt had database sequence 3160. No physical-device screenshot, touch journey or acoustic listening claim is made.
- git diff --check passed. No new simulator was created.

The first UI gesture test swiped the underlying app; targeting the native grabber resolved it. A preferences test tapped an offscreen row underneath the persistent controls; clearance and explicit scrolling were added and the complete path then passed. Low-level simulator taps were unreliable, so XCUITest is the acceptance evidence. Post-test simctl diagnostic collectors were stopped only after tests completed; final passing xcresult finalized successfully. Superseded failed/compile-only result bundles from this task were removed to avoid disk bloat.

English strings are present; the full visual matrix for English, Dynamic Type, Reduce Transparency, dark mode and older iOS remains unverified. Current evidence shows Spanish in light mode. Real voice remains design-only. No deployment, push or merge.
