# Context, return paths and native form polish

October 2, 2026. Local Cuadrao UI preview only.

## Delivered behavior

- Ask Cuadrao is available from account, activity, plan, group, receipt and expanded
  chart details. Existing menus carry the action; details without a menu use a
  quiet labelled action. Home and collection rows stay quiet.
- The active detail presents the same Chat owner in a dismissible sheet. A removable
  chip identifies the chosen record. Chart focus includes the resolved interval,
  currency, space, metric, display and selected category/account kind. Closing the
  sheet preserves the source view. Main Chat uses the same conversation and draft.
- Changing or removing focus preserves text and attachments. Sending retains a
  context snapshot on that turn. Switching regular conversations retains unfinished
  drafts in Recents. Temporary mode retains its privacy and discard rules.
- Home, Accounts and Search open one shared activity detail. Search includes shared
  plans, fixed-currency filtering and archived group destinations. First-use Search
  finds newly saved chats without exposing example conversations.
- Receipt participants and item assignments expose selected/included semantics to
  VoiceOver. Optional location remains removable; denial does not block the receipt.

## Keyboard cause and repair

The retained [debugger stack](keyboard-before-stack.txt) stopped at the exact
invalid-frame branch in SwiftUICore `_FrameLayout.init`. Its caller is SwiftUI
`InputAccessoryBar.body`, through the keyboard accessory's intrinsic size, while
focusing the expense title. This is not a chart or money-value calculation.

Removed the duplicate SwiftUI keyboard toolbars from the affected form family.
Text fields use their native Done key and interactive scroll dismissal. Shared
money inputs keep their existing UIKit Done accessory. The two plain decimal
fields keep a focus-dependent Done control without changing validation.

## Boundaries

Chat state remains local to the running preview. Receipt drafts retain their
existing local persistence. No provider/model call, live context permission
implementation, extraction, backend posting, analytics, cloud upload or payment
behavior was added. Selected references do not grant record access. Physical
camera capture and spoken VoiceOver acceptance are distinct from simulator checks.

## Physical device

Signed build **3419** installed on the paired iPhone 15 running iOS 27.0.1.
Device readback returned version 0.1.0 / build 3419; launch succeeded (PID 6551).
Installation sequence: 2232. The founder then explicitly reported:
**“Scan, Later, and reopen work.”** This closes physical receipt capture/save/reopen
acceptance. It is founder observation, not an automated camera test.

Location allow/remove and denial recovery are simulator acceptance. Native
accessibility labels and large-text layouts are covered below; spoken VoiceOver
on the physical phone was not exercised by the automation.

## Final verification

Application source: **219323e6**. The final native run passed **10/10** journeys,
with zero invalid-frame warnings, including both former keyboard reproductions.
Across the scoped runs, **16 distinct native journeys passed**. Earlier passing
location, first-use Search, group Search, shared-receipt and Home-return evidence
is retained after reviewing the final voice-presentation and account-hit-target
deltas; affected paths were rerun in the final suite. Initial failures and their
subsequent passing results remain in [verification.json](verification.json).

- Receipt state checks: **44 passed**.
- Chat state checks: passed in Spanish and English, including drafts, attachments,
  focus removal, Temporary behavior and nested voice-presentation ownership.
- Modularity budget, Swift parsing and whitespace checks: passed.
- Final scoped code review through **219323e6**: clean, no actionable findings.
- Contextual receipt acceptance includes dark appearance and accessibility text
  size. Permission checks cover allow/remove and denial without blocking review.

This documentation/evidence commit does not change the tested application.

## Retained screenshots

- [Context with unfinished message and attachment](context-group-draft-en.png)
- [Chart period and distribution context](context-chart-selection-en.png)
- [Same draft in main Chat](context-main-chat-continuity-en.png)
- [Receipt context in dark appearance and large text](context-receipt-en.png)
- [Locked voice recording above contextual Chat](context-locked-recording-en.png)
- [Shared activity detail](activity-shared-detail-es.png)
- [Archived group Search](search-group-archived-es.png)
- [Location added](receipt-location-added-en.png) and [denial recovery](receipt-location-denied-en.png)
- [Shared receipt items](receipt-shared-items-es.png) and [confirmed receipt](receipt-confirmed-es.png)
