# Voice surface polish

2026-09-30. Continues founder-approved checkpoint 1dcd12a5d. Scope is native presentation and local preview controls, with no provider, backend, account or microphone implementation.

## Design changes

- Expanded voice has one centered status, a quiet header and a compact material control group. Removed the large brand lockup, explanatory paragraph, simulated spoken sentence and red call-style end button. Mute, typing and ending remain directly reachable with accessible labels.
- Testing actions moved from the main ellipsis menu into the explicit preview information notice. They remain available for inspecting speaking/listening/proposal designs. One notice says the preview is not connected, and its details explicitly state the microphone is off.
- The sea reaches farther into the surface with slow overlapping gradients. Muting fades its intensity instead of resetting the gradient position. Reduce Motion, muted listening and background states pause continuous animation.
- The compact bar retains expand, mute and end. Removed duplicate voice settings from it; expanding gives access to the shared swipeable picker. A small animated waveform uses the same component as expanded voice.
- The composer hides its duplicate start-voice button while voice is active; sending a draft remains available.
- Native sheet dismissal, inline startup, voice persistence across surfaces and keyboard escape remain the same state model. This polish does not implement a second voice lifecycle.

## References

The founder-provided ChatGPT voice settings screenshot remains the picker reference. [Mobbin Copilot voice](https://mobbin.com/screens/dde18761-b196-4a1d-919e-10fbe3421871) was visually reviewed for ambient composition and a compact control group. [Mobbin Meta AI](https://mobbin.com/screens/a13d716b-b9dc-4775-9934-b5c881b221a3) supports maintaining visible conversation alongside voice. These are design references, not claims about current releases or provider behavior.

## Limits

Voice is still a design preview with real bundled voice samples. Animations are illustrative, not measured microphone levels. Spanish and English strings are maintained; this checkpoint's visual evidence is Spanish/light mode. Dark mode, large accessibility text and Reduce Motion device matrices were not fully exercised.

## Verification

Final native build and both focused XCUITests passed (2 tests, zero failures, 55.180 seconds): silence on picker open, swiping/playing/stopping real samples, saved voice across Profile and relaunch, expanded mute state, proposal handoff, grabber swipe-down, typing then dismissing the keyboard, compact mute, cross-surface navigation and explicit ending. The empty composer no longer exposes a duplicate start-voice action during voice.

Screenshots are exported unchanged from final-source Test-ArgusFoundation-2026.09.30_23-53-11--0500.xcresult. Tests were run only on reserved simulator 8AFB6084-8918-416E-9164-E21061306BEC; the existing DerivedData cache was reused. git diff --check passed. The run's post-test diagnostic collector was stopped after XCTest completed, and the result finalized with exit zero.

Final signed physical-device build passed and installed on iPhone 00008120-001428C90E04201E as local.cuadrao.design.47R3855RTJ, receipt sequence 3176. The first launch attempt encountered a device disconnection after installation. No physical touch or acoustic verification is claimed. The prior in-turn test bundle was removed; final passing results and screenshots are retained.

The launch retry confirmed the phone was locked (FBSOpenApplicationErrorDomain 7). Installation is complete; opening Cuadrao Preview after unlocking remains a founder action. No push, merge or deployment.
