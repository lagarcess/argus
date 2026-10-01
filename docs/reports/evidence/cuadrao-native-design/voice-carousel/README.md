# Swipeable voice picker

2026-09-30. Supersedes the list picker in voice-companion checkpoint a9c209d5. Based on the founder-provided ChatGPT voice settings screenshot: a compact sheet, a single voice and description, horizontal paging and dots, with the voice surface still visible behind it.

Swiping or tapping a page dot immediately saves and previews that voice. Opening the sheet is silent. Replay/stop is explicit; closing or backgrounding stops sample playback. Profile and both voice controls read one AppStorage preference. Voice sound remains separate from response tone. Existing genuine bundled Ara/Eve/Sal samples are unchanged; English sample language is disclosed. No new language preference, microphone capture, provider connection, backend change or real agent action.

The native sheet starts at 360 points, can expand, and uses a large detent for accessibility text sizes. Page dots have 44-point targets and spoken names/selected traits. Spanish and English copy are included.

## Verification

- Simulator build passed on reserved simulator 8AFB6084-8918-416E-9164-E21061306BEC.
- Focused native test testVoiceChoiceAndProposalHandoff passed in 36.476 seconds: silent open, actual horizontal swipes Ara to Eve to Sal, automatic sample playback, stopping the sample, shared Sal preference in Profile, proposal handoff with voice still active, and selection retained after relaunch.
- Screenshot exported unchanged from that passing run, Test-ArgusFoundation-2026.09.30_23-38-06--0500.xcresult. Reviewed visually in Spanish/light mode.
- Initial test attempts targeted an unexposed container identifier, then a short text-bound swipe. A full-width gesture anchored to the visible title exercised native paging successfully. App code did not change during those test corrections.
- Physical iPhone signed build passed using the existing single DerivedData folder. No new simulator or build cache was created.
- Full English, dark mode and accessibility visual matrices were not rerun. Real voice remains a design preview with playable samples.

Installed and launched Cuadrao Preview (local.cuadrao.design.47R3855RTJ) on paired iPhone 00008120-001428C90E04201E; install receipt sequence 3168. Physical touch/acoustic validation remains with the founder. Removed only this turn's two superseded failed test bundles (about 118 MB); retained the passing result and durable screenshot. No push, merge or deployment.
