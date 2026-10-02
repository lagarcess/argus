# Profile follow-up UI acceptance — October 2, 2026

Final app source: `55baed872`. Preview branch: `codex/cuadrao-design-scan-recents`.
UI only: photos and feedback remain session-local. No server upload, feedback
submission, auth mutation or production service change.

## Verified journeys

Six distinct native journeys passed across focused runs on iPhone 18 Pro / iOS 27:

- Native Photos picker: select a real library image, cancel without changing the
  profile, save, reopen, remove/cancel, then remove/save. The fixture image is a
  preview screenshot, not personal media.
- Feedback: general/problem/idea drafts survive switching; a partial problem can
  be saved and reopened; editing clears the saved indicator.
- Profile: Sign out is visible and tappable above the custom navigation at normal
  and accessibility text sizes. Its existing preview alert is preserved.
- Settings: main tabs hide while pushed; native Back restores Profile navigation;
  Help to Feedback and nested return paths remain intact.
- Existing profile Save/Cancel and validation regression.
- Existing dark English larger-text support regression.

The first run passed four journeys but two automation locators missed their native
controls. Corrected the native menu target and Photos grid accessibility identifier;
those two journeys then passed. Final source removes repeated feedback placeholders
and preserves explicit accessibility labels. Feedback and larger-text navigation
were rerun successfully at `55baed872`.

| Run | Result | App source |
| --- | --- | --- |
| `test_sim_2026-10-02T17-40-22-600Z_pid5473_be5c8c23` | 4 passed; 2 locator failures corrected | `fadf46e38` |
| `test_sim_2026-10-02T17-43-40-009Z_pid5473_59b037a0` | 2 passed | `fadf46e38` |
| `test_sim_2026-10-02T17-49-44-583Z_pid5473_94af1567` | 2 passed | `55baed872` |

Scoped final code review: clean, including the final field-label delta.
Modularity budget and `git diff --check`: pass. Signed iPhone build 3413 succeeds. Installation was retried after the founder
reconnected the phone; device readback confirms bundle version 3413, and launch
succeeded on `00008120-001428C90E04201E`. Physical touch acceptance remains with
the founder; native interaction tests above ran on the simulator.

## Visual evidence

- [Before: obscured Sign out](before-signout-obscured.jpg), source `8ec419b3`.
- [Sign out clearance](profile-signout-clearance.png), source `fadf46e38`.
- [Photo selected](profile-photo-draft.png), source `fadf46e38`.
- [Dark English settings](settings-dark-large-en.png), source `fadf46e38`.
- [General feedback](feedback-general-draft.png), final source.
- [Partial problem saved](feedback-partial-bug-saved.png), final source.
- [Larger-text feedback without tabs](feedback-large-without-tabs.png), final source.
- [Larger-text Sign out clearance](profile-signout-large-clearance.png), final source.

Retained `fadf46e38` photos/navigation evidence is revalidated by source comparison:
the only subsequent app change is the feedback placeholder/accessibility label.
The final source was visually inspected from native screenshots. Documentation
and evidence commits after that source do not change the installed application.

## Connected work

The main execution board C07/C08 retains server avatar storage/upload, durable
feedback intake, identity and settings ownership. The design guide records local
Save/Cancel, one active avatar and Settings navigation behavior. No new parallel
roadmap is introduced here.
