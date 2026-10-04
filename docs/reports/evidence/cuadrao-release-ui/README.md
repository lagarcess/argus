# Cuadrao release UI checkpoint

UI handoff, October 2, 2026. This checkpoint implements the founder's 17-item
presentation scope and the subsequent avatar correction. It does not establish
external TestFlight readiness or connected service acceptance.

## Integration reconciliation, October 3, 2026

Merge commit `ad0532f1` brings integration `a8c37d3a` into this branch with a plain
merge. The guide's conflict and the board and MVEE duplicates that the auto-merge
created were resolved toward the October 2 locks and the six-lane handoff. Later
commits finish the handoff's ten pickup items. Code head for this run: `c82f093d`.
Simulator: iPhone 18 Pro Max, Xcode 27. This run does not certify connected or
physical-device journeys, TestFlight readiness or any service behaviour.

- `CuadraoFirstRelease` hides the unfinished Profile rows, photo selection and
  conversation bulk actions only in release builds. DEBUG builds show all of them,
  and `--cuadrao-release-gates` previews the release set in DEBUG.
- Temporary-chat memory copy follows `CuadraoFirstRelease.shows(.memory)`.
- The deletion fixture uses Iris's locked shared-plans copy verbatim. In progress
  (`202`, or `503 account_deletion_incomplete`) is a signed-out confirmation that
  never becomes the finished state. It stays a DEBUG fixture; nothing calls
  `POST /account/delete` from iOS yet.
- A Release build for the simulator compiles. Its binary contains no
  `--cuadrao-release-gates` string, and the default and `--cuadrao-design` launches
  show no Apple or Google button:
  [default](2026-10-03-w1/release-default-launch-light.png),
  [design welcome](2026-10-03-w1/release-design-launch-light.png).

Results, all on the simulator above:

| Run | Head | Result |
| --- | --- | --- |
| `verify.sh build` (Debug) | `860a6044` | Build succeeded |
| Release build for the simulator | `860a6044` working tree | Build succeeded |
| Preview state checks (`cuadrao-design-mac-pass.sh checks`) | `860a6044` | All six runners passed: 80 Home balance, 58 Plan, 50 group, 44 receipt, 213 avatar crop, 10 temporary chat. [Log](2026-10-03-w1/design-preview-checks.txt) |
| Full `verify.sh test` | `860a6044` | 146 tests: 88 passed, 47 skipped, 11 failed. [Per test](2026-10-03-w1/full-suite-860a6044.txt) |
| Focused pickup runs | pre-commit tree, then `860a6044` | [Items 1 to 4 and 7](2026-10-03-w1/focused-pickup-items.txt), [feedback reveal](2026-10-03-w1/focused-feedback.txt), [auth-on sign-in](2026-10-03-w1/focused-auth-signin.txt) |
| Focused rerun of full-suite failures | `c82f093d` | [Results](2026-10-03-w1/focused-c82f093d.txt) |

Of the 11 full-suite failures, `CuadraoHomeChartUITests.testFirstObservationAndFirstExpense`
still expected a dash for first use; `c82f093d` asserts Sin datos and the focused rerun
passes. `CuadraoReceiptPermissionUITests.testAllowedLocationCanBeRemoved` needed the
checklist's simulator location and passes once it is set. Two are in #790's area and
still fail in the focused rerun: `ReleaseUIJourneyTests.testUpdatesNoDataAndReadOnlyHistory`
(the back step after opening the first notice lands on the review root, so the Data link
is gone) and `CuadraoSupportUITests.testHomeActivityReturnsToSameRow` (the returned row
sits under the floating tab bar and is not hittable). The other seven touch code #790 does
not change (#785 planning, groups, receipts and scan, and a connected fixture test that
needs its environment) and were not investigated here.

The Mac pass `screens` step and its auth-on sign-in rerun were not run as a whole: the
shared-Mac lock order arrived first. The auth-on sign-in check passed on its own.

## Combined preview update for build 3420

PR #786 is included through integration `0ea81a208668e0391aaf008412716f6cae38826c`.
Reconciliation commit `a73c331f` includes the full Home, Search, Updates, Profile
and Settings preview, alongside #790's release views. Source/test checkpoint
`519cfa5f` passed the [combined native journeys](combined-preview-tests.json).

The preview and connected Profile now use one avatar selection/renderer and one
photo decoding/crop implementation. Photos are available in the full preview;
none keeps the tab icon, while settings show the camera circle. The full profile
editor retains name and preferred-name editing. Hold Home's greeting →
**Revisión de lanzamiento / Release UI review** to inspect pending release flows.

The confirmed-zero rule is reconciled across hero, comparison and averages.
Explicit continuous coverage with no expenses means zero, even with no expense
rows; missing coverage cannot manufacture zero. Comparisons report an amount,
never a percentage. All 80 Home projection checks passed on the combined source.
The 25 Updates and identity checks retain their unchanged-source evidence.
Modularity and whitespace checks passed after reconciliation.

- [Full Profile empty state](full-profile-empty-es.png)
- [Full Profile selected avatar](full-profile-theme-es.png)
- [Home with selected avatar](full-home-theme-es.png)
- [Shared photo crop](combined-photo-crop-dark-en.png)
- [Shared photo tab](combined-photo-tab-dark-en.png)

Cuadrao Preview **3420 is installed on the physical iPhone 15**. The device
readback confirmed name, bundle and build after installation. The signed build
uses the existing bundle `local.cuadrao.design.47R3855RTJ`, auth disabled and
`CUADRAO_DESIGN_PREVIEW=true`. A device-only copy of the canonical Info.plist sets
`CFBundleDisplayName` to Cuadrao Preview; no production configuration was changed.

The initial wireless RSD failure recovered after the user made the phone ready.
Remote launch was subsequently denied because the device locked. Installation
is confirmed; opening and interacting with this build on the physical phone is
not claimed. The user can tap the installed app. See [delivery record](device-3420.json).
No provisioning or trust settings were changed.

## Review entry

Build ArgusFoundation in Debug with `CUADRAO_DESIGN_PREVIEW=true`, then launch
`--cuadrao-release-ui`. Add `--release-dark` for dark appearance; use system
language and Dynamic Type settings for localization/accessibility review.
The DEBUG-only host has explicit fixture outcomes. Choosing an outcome does not
modify authentication, admission, Household membership or financial records.

The connected Profile uses the shared avatar editor and signed-in legal links.
Its pushed settings hide the tab bar. The connected Household admin invitation
uses the shared QR/link presentation and retains existing model commands.
Connected Updates explicitly shows unavailable until an inbox source is supplied.

## Delivered and graft boundaries

| Items | UI supplied | Service facts/actions required at graft |
| --- | --- | --- |
| 1 | Deletion consequences, code/typed confirmation, resend, pending, retry, finish | Verified deletion result, admin succession, history removal, revocation and actual sign-out; shared-plan retention follows six-lane contract |
| 2 | Signed-in legal destinations | Links derive from the existing configured web URL; live page content is not certified here |
| 3 | Apple and Google, loading/cancel/error/name recovery | Provider authentication, name persistence and pending invitation continuation; connected auth remains email until graft |
| 4–8 | Admission gate/waitlist, quota, share/code/QR, capped/expiring founder links, real Household invitation presentation | Server admission, quota, group capacity, authoritative link/code and expiry; Household membership alone does not expose accounts |
| 6, 9, 11 | Accepted/admin/history/closed notices, bill reminder and push opt-in states | Durable inbox, bill occurrence scheduler, paid/cancelled suppression, notification permission/registration and source authorization |
| 10 | Missing month distinct from recorded zero; amount delta and honest comparison availability | Existing financial history must supply coverage; missing records cannot certify zero spending |
| 12 | Muted, labelled read-only moved history | Explicit move provenance/cutoff; view-only permission does not imply an account move |
| 13–14 | No email notification toggle or unsupported settings rows; shared avatar selection | Initials/themes/photo are local session state. Hosted photo storage, profile persistence and cross-device sync remain pending |
| 15 | Disclosure, scoped data/provider facts, allow/decline and recovery | Consent version and enforcement before every model-dispatch entry; fixture provider text is not production configuration |
| 16–17 | Source disconnect and memory off/reset states | Feature availability, actual connections/memory and acknowledged mutation callbacks |

An unset Profile tab keeps its existing glyph. Selected initials/themes have no
added circle, and photos have only their circular crop. Settings/editor keep a
circular frame; the empty circle contains a camera with an add badge. Save commits
the editor draft; Cancel leaves the selection unchanged. One typed selection owns
both surfaces, applying Model the Domain rather than competing optional fields.

## Verification and evidence

- Initial acceptance used iPhone 18 Pro simulator, iOS 27. The combined update above records the later physical installation.
- Nine distinct native journeys have passing evidence. The integrated run passed
  eight and missed the photo picker with a fixed-coordinate tap. The test now
  waits for the native photo image accessibility element. All three avatar journeys
  then passed, including photo selection → crop → Save → tab → reopen.
- Native coverage includes Spanish, English, large Dynamic Type, dark photos,
  deletion resend/cancel/pending/finish, social cancellation/name recovery,
  invitation full/quota presentation, Updates/no-data/read-only and AI decline.
- 25 Updates checks, 79 Home projection checks and identity-state checks passed.
  Swift macro compilation required running outside the nested process sandbox.
- Modularity budget passed on the reconciled tree. Diff whitespace checks passed.
- QR decoding was checked by the invitation worker with Vision for custom-scheme
  and universal URLs. No external acceptance or short-code service was invoked.
- Independent deletion delta review returned clean after the resend and cancellation
  repairs. Final avatar review inspected actual screenshots, catching and fixing an
  unsupported camera symbol before these final captures.

[Integrated test summary](integrated-tests.json) records the original selector
failure; [avatar retest](avatar-tests.json) records its resolution. Passing evidence
for the six unaffected journeys is retained. Screenshots below are committed,
not temporary-only evidence. This applies Prove It Works to the native result.

| Evidence | What it shows |
| --- | --- |
| [Empty profile](profile-empty-circle-es.png) | Settings camera circle beside unchanged Profile tab |
| [Theme avatar](theme-tab-unframed-es.png) | Framed settings avatar and unframed tab artwork |
| [Default restored](avatar-default-restored-es.png) | Circular empty editor and native trailing selection check |
| [Large text](avatar-initials-large-en.png) | English initials and accessibility text size |
| [Photo crop](photo-crop-dark-en.png) / [photo tab](photo-tab-dark-en.png) | Native picker/crop and selected photo in dark appearance |
| [Deletion pending](deletion-pending-es.png) / [cancelled verification](verification-cancelled-en.png) | Recovery controls and cancellation return |
| [Social name](social-name-en.png) | Missing-name recovery without fake authentication |
| [Invitation full](invitation-full-es.png) / [quota](personal-invitation-es.png) | Waitlist and personal-invitation presentation |
| [Bill notice](bill-notice-es.png) / [data truth](no-data-moved-history-es.png) | Reminder detail and no-data/read-only specimens |
| [AI consent](ai-consent-en.png) | Scoped sharing explanation and decline action |

## Initial integration and review disposition

- Original integration base: `58ace0f74d81df41f23244a82ad98ad1c736f061`.
- Current fetched integration: `900178b32df1b25a08f8d15bdbbe82485ae61c80`.
- One-way reconciliation merge: `e893bacac47ffdacf34d403a2a855f5e0bb9d093`.
- Final runtime/test source: `cda15b03c7702428e27a5d47028af6ec5f71cf97`. Following evidence/roadmap changes are
  documentation-only and do not change the verified source.
- Semantic overlap: integration added Plan, receipts, contextual chat and preview
  activation. The palette conflict preserves `CuadraoDesignPreview.isActive` and
  the DEBUG review appearance. No API, migration, permission, environment contract,
  analytics or model instruction changed in this lane. The full nine-journey run
  followed reconciliation; the final avatar delta reran its three affected journeys.
- No merge to integration, deployment, hosted operation, live OAuth/deletion/AI,
  physical-phone journey or external TestFlight submission was performed.
- GitHub CI status belongs to the PR. This is a UI handoff, not a READY report.

The [main execution board](../../../specs/argus-execution-board.md#cuadrao-release-ui-landing-order)
owns remaining delivery work. The [design guide](../../../../.agent/designs/cuadrao/DESIGN.md)
owns stable patterns and the visually inspected Mobbin references.
