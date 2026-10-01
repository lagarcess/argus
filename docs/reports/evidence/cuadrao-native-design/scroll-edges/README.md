# Native scroll-edge checkpoint

Design-only Cuadrao preview, 2026-09-30. Shared SwiftUI scroll chrome replaces hard clipping at stationary controls.

## References

- Original HTML: argus-type-preview/scroll-edges.css. Six-pixel backdrop blur, masked top and bottom transitions; shorter bottom treatment in chat. The original is the behavior reference, not a second native implementation.
- [ChatGPT on Mobbin](https://mobbin.com/screens/56b5c3db-8289-4ee9-b705-c3b5bcc50e53): visually inspected messages passing beneath softened top controls and a floating composer. Static reference does not establish gesture behavior.
- [Apple scroll edge styles](https://developer.apple.com/documentation/swiftui/scrolledgeeffectstyle): native soft blur transitions between content and controls.

## Implementation

CuadraoScrollChrome owns the native soft style and safe-area bars. Chat header and composer register as bars, including the compact voice preview. Search keeps controls legible with a light backing and full-width scroll effects. Shared bottom navigation uses the same bar treatment. Forms, onboarding and the voice animation were not redesigned.

iOS 26+ uses the system soft scroll edge. Older iOS uses safe-area insets with regular material, without the progressive native effect. Older-iOS appearance was not run. There is no per-frame blur animation, private filter, new copy or new provider behavior.

## Verification

- Native simulator build passed with no diagnostics on reserved device 8AFB6084-8918-416E-9164-E21061306BEC; existing DerivedData reused.
- Chat: scrolled an example response beneath the header; controls stay sharp and selectable. Final-build screenshot: chat.jpg.
- Voice preview: expanded -> keyboard -> type draft -> hide keyboard. Navigation returns, draft remains, compact voice remains; Search is reachable. voice-keyboard.jpg was captured before a Search-only backing adjustment and whitespace formatting; the Chat/voice code is unchanged in the final build.
- Search: scrolled accounts to plans/chats/files/memory; header controls stay legible, bottom navigation remains reachable. Final-build screenshot: search.jpg.
- Home: initial visual check showed the soft bottom transition and unchanged layout/navigation.
- git diff --check passed. No new tests for this reversible visual change. No physical-iPhone verification or installation in this checkpoint.

Screenshots and this note accompany the source checkpoint. No backend, API, provider or persistent financial state changes.
