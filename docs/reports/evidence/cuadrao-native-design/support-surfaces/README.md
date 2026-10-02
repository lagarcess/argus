# Cuadrao support surfaces — October 2, 2026

UI-only Search, Profile, Settings and Updates polish on
`codex/cuadrao-design-scan-recents`.

## Scope and source

App source: `34e23142` (last app change). Final test source: `8e468b2e`.
Later changes in this checkpoint are documentation and retained screenshots only.
Search opens the actual preview plans, preserves query/filter context on Chat
return, and exposes usable empty-state recovery. Profile uses shared avatar
colours/icons and preserves Save/Cancel; Home reads its preferred name. Settings
reuse the currency menu and native quiet-hour controls. Updates derives contextual
account/plan rows and the bell count from the same owners, keeps read state,
and opens real preview detail pages with a local Back path.

## Verification

Five new native journeys passed across focused final runs on iPhone 18 Pro,
iOS 27 simulator:

- Profile theme/name save, cancel, Home greeting and invalid empty name.
- Search actual plan detail, Chat return, no-match recovery and Household filter.
- Updates account/plan return, read/unread by hold and swipe, badge, reopening,
  mark-all, unread empty state and quiet-hours controls.
- First-use Updates and empty Plans perspective.
- English dark mode with accessibility text sizing across all four surfaces.

The existing shared Search/date/large-text regression also passed. The first runs
identified an inherited accessibility identifier overriding Search recovery
controls and test interactions that missed the native switch, combined picker
labels and lazy result rows. The identifier was fixed in the app; test selectors
and presentation capture timing were corrected. Affected journeys then passed.

Result bundles (local diagnostic provenance):
- `test_sim_2026-10-02T16-54-42-456Z_pid5473_422e0610.xcresult`: existing regression passed.
- `test_sim_2026-10-02T17-01-12-860Z_pid5473_95218505.xcresult`: four support journeys passed; Search subsequently corrected.
- `test_sim_2026-10-02T17-06-00-919Z_pid5473_2a003318.xcresult`: final Search journey passed.

The committed PNGs preserve the visible evidence. The four passed journeys retain
the same app source and test bodies at the final checkpoint; only Search test
selectors changed afterward. Modularity budget and whitespace checks passed.
Final scoped review returned clean after the deleted-space Search destination
and accessibility identifier fixes. No backend or provider behavior changed.

## iPhone delivery

Signed build **3412**, bundle `local.cuadrao.design.47R3855RTJ`, installed on the
founder’s iPhone and verified through the device application inventory.
Automatic launch was denied because the phone was locked. Physical touch
acceptance is not claimed; the founder can open Cuadrao Preview after unlocking.

## Preview boundaries

Updates are contextual source summaries, not invented dated financial events.
Read state and edited profile fields persist during the preview session, not
across app relaunch. Quiet hours and delivery switches do not schedule or send
notifications. No permissions, photo upload, remote account changes or backend
connections were added. Future work stays on the main execution board.

## References

- [Airbnb grouped settings](https://mobbin.com/screens/936fbfe8-4c12-4c69-95f0-6c56b7dede64)
- [Superlist Updates](https://mobbin.com/screens/f8cf46ce-c9c0-4041-b707-202046a06247)
- [ClickUp search](https://mobbin.com/screens/b86be07c-0f16-46c4-bd1b-2d46b8a83390)
