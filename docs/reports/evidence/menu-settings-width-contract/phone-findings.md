# 390px menus/settings audit

Deterministic local browser fixtures, dark mode, 390x900 CSS pixels, English and es-419, guest and registered identities. API writes/external network blocked; no turns, simulations, account mutations, feedback submissions or sign-outs. The repository's pinned Playwright runner drives the local server.

## Existing inconsistencies to report, not fix

- Profile stays a centered 358px dialog at 390px; other settings are bottom sheets. Display/preferred-name edit Save/Cancel controls measure 22x 22px; Close is 28x 28px; App language is approximately 27x 24px. The nested language choices are 35.5px high. Evidence: `phone-registered-{en,es-419}-{profile,display-name,preferred-name,profile-language,avatar}.png`.
- The registered Recents row menu remains a 160px anchored popover with 35.5px-high actions at 390px. The Search row menu uses 44px actions. Evidence: `phone-registered-{en,es-419}-{recents-menu,search-row-menu}.png`.
- Archived and recently deleted rows use 36x 36px Restore buttons, below the menu/sheet 44px target. The Restore accessible label is hardcoded English even in Spanish; screenshot labels are icon-only. Evidence: `phone-registered-es-419-{archived,deleted}.png`, geometry JSON and `web/components/settings/ArchivedChatsView.tsx` / `DeletedItemsView.tsx`.
- **Account deletion is obscured:** tapping Delete account creates a centered dialog with z-index 80, behind the Data Controls BottomSheet at z-index 120. Both locales show the parent sheet instead of the account request. Dedicated center/control hit-tests record this; DOM visibility alone did not catch it. Evidence: `phone-registered-{en,es-419}-occluded-account-delete.png` and phone-occlusion.jsonl. No account request was submitted.
- Delete conversation/delete-all confirmations remain centered dialogs. English confirmation actions are 37.5px high; Spanish wraps into taller buttons. Evidence: `phone-registered-{en,es-419}-{header-delete,delete-all-confirm}.png`.
- Header rename uses a sheet, but Save/Cancel remain 36px high. Evidence: `phone-registered-{en,es-419}-header-rename.png`.
- Assistant More Actions stays a 220px anchored popover. Its menu rows are large enough; the trigger and adjacent rating controls remain small. Evidence: `phone-{guest,registered}-{en,es-419}-assistant-more.png`.
- Feedback's Learn more text button is only 19.5px high and has no click handler in `FeedbackDialog.tsx`. This is a pre-existing dead control, not exercised as an external navigation. Evidence: feedback screenshots plus source.

No measured horizontal overflow in the captured dialog/menu surfaces. The Profile language picker extends below its parent dialog while remaining inside this viewport; no clipping observed. This desktop Chromium viewport audit does not simulate the phone's on-screen keyboard.

## Availability and scope

Shared links is absent in this release fixture (feature flag off); its two locale tests explicitly skip. Memory/Personalization is absent because backend availability is false. Sidebar preferences and keyboard shortcuts are intentionally not offered from the phone drawer. Guests have no profile/account-management/header-owner menu; guest Search still has a reachable Conversation actions menu. Guest theme controls are captured in the Settings root; no setting is changed. Help/legal links and Security are opened read-only. Destructive controls stop at confirmation UI.


## Screenshots and measurements

- Account deletion: [English](darwin/phone-registered-en-occluded-account-delete.png), [Spanish](darwin/phone-registered-es-419-occluded-account-delete.png), [hit-test evidence](phone-occlusion.jsonl).
- Profile: [profile](darwin/phone-registered-en-profile.png), [name editor](darwin/phone-registered-en-display-name.png), [Spanish language picker](darwin/phone-registered-es-419-profile-language.png).
- Row menus: [Recents](darwin/phone-registered-en-recents-menu.png), [Search](darwin/phone-registered-en-search-row-menu.png), [guest Search](darwin/phone-guest-es-419-search-row-menu.png).
- Restore controls: [archived](darwin/phone-registered-es-419-archived.png), [deleted](darwin/phone-registered-es-419-deleted.png).
- Confirmation: [delete all](darwin/phone-registered-en-delete-all-confirm.png), [delete chat](darwin/phone-registered-en-header-delete.png), [rename](darwin/phone-registered-en-header-rename.png).
- Assistant and Feedback: [guest More](darwin/phone-guest-en-assistant-more.png), [Feedback](darwin/phone-registered-en-feedback-general.png).
- [Per-surface geometry](phone-geometry.jsonl).

No production fix for these findings is included. The blocked account request
needs a separately scoped overlay-ownership fix; DOM visibility alone is not
proof that a modal is usable.
