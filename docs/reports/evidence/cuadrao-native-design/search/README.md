# Cuadrao Search and phone preview

September 30, 2026. Native UI-only continuation of the locked September 28 search study.

## Scope and provenance

- Uses the quiet field, category strip and grouped results from the locked HTML navigation.js/search-unified.png reference.
- Categories: Todo, Cuentas, Movimientos, Planes, Chats, Archivos, Memoria. Horizontal scrolling reveals remaining categories.
- Accounts/activity derive directly from the same observable preview owner used by Home. Plans/chats/files/memory are explicit design examples, not financial/API implementation.
- Memory source-conversation drill-through is implemented; real correction/deletion/suppression remains with the eventual canonical owner. File preview explicitly says it contains no real PDF.
- Scope/currency filters are presentation controls, not a permission model. Private reference examples never appear under Hogar.
- [Notion filter reference](https://mobbin.com/screens/ae3beaf9-9095-4831-ae5e-430bb28d9dd4) inspected inline on Mobbin.
- [Apple search guidance](https://developer.apple.com/design/human-interface-guidelines/searching): make search scope clear.

## Verified

Simulator build succeeded without compiler warnings/errors. Visually inspected grouped results and Memory category (memory.jpg). Navigated account result -> existing account detail -> back with category retained. Opened native filter sheet. Scrolled category strip; opened Memory -> detail -> source conversation -> back -> Memory results with selection retained.

Physical iPhone build succeeded; only AppIntents metadata extraction warning (no AppIntents dependency). Installed and launched separate bundle local.cuadrao.design.47R3855RTJ, named Cuadrao Preview, without any launch arguments. A first wireless launch disconnected; retry succeeded, as did installation/launch after the expanded Search categories. No physical-device screenshot or complete device interaction journey was captured.

Keyboard typing through the automation bridge did not change the field and is NOT accepted as successful text-entry testing. Real typing, no-results/recovery, every filter combination, English rendering, large text and VoiceOver still need verification. Strings for new UI include Spanish and English.

## Reproduce local preview

Reuse ios/ArgusFoundation.xcodeproj, ArgusFoundation scheme and /private/tmp/cuadrao-native-design-build. Simulator: existing iPhone 18 Pro, local.cuadrao.design; launch --cuadrao-design --cuadrao-home --home-populated, AppleLanguages (es), AppleLocale es_DO.

Device build overrides: SUPPORTED_PLATFORMS=iphoneos, CODE_SIGN_STYLE=Automatic, CODE_SIGNING_ALLOWED=YES, CODE_SIGNING_REQUIRED=YES, CODE_SIGN_IDENTITY=Apple Development, empty CODE_SIGN_ENTITLEMENTS, existing approved DEVELOPMENT_TEAM, distinct ARGUS_LOCAL_BUNDLE_IDENTIFIER, ARGUS_DISPLAY_NAME=Cuadrao Preview, CUADRAO_DESIGN_PREVIEW=true, ARGUS_AUTH_ENABLED=false. Use the paired device destination. These overrides are opt-in; do not rewrite the connected app configuration.

One build cache was reused; no simulator was created. No backend, hosted setting, real invitation, financial record or model call changed.
