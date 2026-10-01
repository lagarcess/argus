# Recents dates and swipe colors · October 1, 2026

Supersedes the visible row ellipsis in the prior Scan/Recents checkpoint.
[Canonical design decision](../../../../../.agent/designs/argus/DESIGN.md#cuadrao-native-capture-and-recents-decisions--october-1-2026).

- Last-message date replaces the visible menu button. Hold opens the same actions;
  the shared action builder also supplies VoiceOver actions.
- Pin/unpin is amber; archive is slate; restore uses Cuadrao green. Symbols and
  labels remain present. Delete remains a red contextual action with confirmation.
- Chat turns own their timestamps. Recents and Search derive the same date;
  renaming, pinning, unread and archive state cannot change it. Recent rows sort
  by last-message time within their pinned/recent groups.
- Hoy/Ayer and Today/Yesterday use local calendar days. Older dates use locale
  formatting and include the year when needed. Unknown dates stay absent.
  Display labels refresh every minute while visible. Example chats have sample
  dates; this remains an in-memory design preview, not backend persistence.

## References inspected

[Fiverr amber star](https://mobbin.com/screens/d6624e4d-927d-46b3-a3f1-d763ef7dd04a),
[Telegram gray archive](https://mobbin.com/screens/7b4ae82f-5122-4626-82c9-a6ef11bea8dc),
[Manus dates and contextual actions](https://mobbin.com/screens/824cf0e4-1752-4208-81d5-16c3c60c0b27).
Cuadrao's exact colors and gesture mapping are adaptations.
[Apple accessibility actions](https://developer.apple.com/documentation/swiftui/accessible-controls)
provide the non-gesture route to the same commands.

## Verification

Three native UI journeys passed: hold menu plus pin/rename/archive/restore/delete
recovery; Spanish/English labels and Scan regression; shared Search/Recents dates
at a larger text size. Screenshots are from those passing runs on the reserved
Cuadrao iPhone 18 Pro simulator. App-source digests match both runs; only the
additional Search test was added between them. No app-source changes followed.

Actual preview model checks passed in both languages, including local calendar
DST boundaries, prior-year labels, absent dates, metadata edits retaining the
last-message date, and new messages advancing it. Existing temporary-chat and
voice-state checks also passed. Source: `ios/DesignPreviewTests/TemporaryChatChecks.swift`.
VoiceOver actions are implemented via the shared native builder; manual VoiceOver
operation and physical-device gesture QA are not claimed.

The screenshot files here cover the quiet row, each swipe color, hold menu,
recovery, English menu, and Search/Recents with larger text.

## Physical delivery

Signed iPhone build succeeded; installed and launched `Cuadrao Preview` on the
user's iPhone 15. Bundle `local.cuadrao.design.47R3855RTJ`, receipt sequence **3232**.
