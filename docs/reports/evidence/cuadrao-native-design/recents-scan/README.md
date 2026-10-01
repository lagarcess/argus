# Scan and Recents design checkpoint · October 1, 2026

The [design decision](../../../../../.agent/designs/argus/DESIGN.md#cuadrao-native-capture-and-recents-decisions--october-1-2026)
locks Escanear/Scan and the future Apple document scanner, plus the approved
Recents gestures and row hierarchy. No camera, microphone, provider or backend
integration is enabled by this checkpoint.

## Verification

- Final native XCTest run: two journeys passed, zero failures. Recents covers
  pin by swipe, mark unread, rename, archive by swipe, restore, confirmed delete,
  recovery by opening, and current-chat identity. The second journey checks
  Spanish/English Scan entry, sample attachment, scopes and English menu labels.
- Actual preview model checks pass in Spanish and English: archive/delete leave
  an active conversation safely, preserve its draft, stop its voice session,
  and restore the same object. Existing temporary-chat and voice checks pass.
- Native simulator: dedicated Cuadrao iPhone 18 Pro, iOS 27. Screenshots below
  are from the final passing run. Source digests are retained alongside them;
  source files were unchanged after these captures through the checkpoint commit.
- Signed physical iPhone build succeeded. Installation/launch receipt is recorded
  below separately; simulator checks do not claim hands-on physical-device QA.
- Earlier exploratory checks failed on automated native-alert keyboard/tap timing.
  The final test waits for the keyboard transition, reads back edited text and
  verifies the alert closes before asserting the saved row title.

Run focused UI verification with `CuadraoHistoryDesignUITests` in the
ArgusFoundation scheme, `CUADRAO_DESIGN_PREVIEW=true`, `ARGUS_AUTH_ENABLED=false`.
Run shared state checks with `python3 ios/DesignPreviewTests/run_temporary_chat.py`.

## Captures

- [Spanish Scan entry](scan-spanish.png) / [English](scan-english.png)
- [Title-first Recents](recents-spanish.png)
- [Spanish menu](recents-menu.png) / [English menu](recents-menu-english.png)
- [Saved rename, pinned and unread](recents-renamed.png)
- [Native archive swipe](recents-archive-gesture.png)
- [Recoverable deleted chat](recents-deleted-recovery.png)

Scan currently opens the honest sample-attachment preview. Apple's native scanner
is the locked future capture choice, not an implemented or shipped capability.
Recents data remains local design state and resets on app relaunch.

## Physical delivery

Installed and launched `Cuadrao Preview` on the authorized iPhone 15.
Bundle: `local.cuadrao.design.47R3855RTJ`; installation receipt sequence **3224**.
