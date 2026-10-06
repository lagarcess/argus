# Full Cuadrao interface recovery

The approved Preview interface is the presentation source. Connected records use
those same view bodies. This replaces the narrow money-only completion recorded
in the parent report. Verification is still in progress; this is not a release
or physical-device acceptance claim.

## Ownership and source

| Item | Source |
| --- | --- |
| Approved Preview source | `5753b5d7cb3e4a13b4bac58a87fa32127b6fcf37` |
| Original integration base | `875de09ac2115acec42e09060b92878aa5f18eff` |
| Integration used for this recovery | `7018e0edebbc370b999005a857230bf3c3a1ad8b` |
| One-way reconciliation merge | `9b85a4a1329d1cdcaf574f71f325993420bf3eb9` |
| Latest integration | `70b0cd3891937f026900aceb96ce5f556c76b0b3` |
| Privacy reconciliation merge | `0a512315142c8d59b71146b0e24e1848072634e2` |
| Currency reconciliation merge | `2808ae2c1` |
| First full-shell checkpoint | `e6b7cf325187f0c717634ab750cc258025bbf9a9` |
| Linked Plan detail recovery | `ba8c9e4f1` |
| Navigation/accessibility correction | `40b2c45d0` |
| Receipt draft and journey checkpoint | `16ef25322` |
| Native Plan and account return | `dfe8644cd` |
| Native return test drivers | `87b5b77f1` |

The trust and privacy lane acknowledged the presentation handoff. It retains
auth, sessions, deletion, consent, and operations. This lane retains the shared
Cuadrao interface. PR #864 remains separately owned; its recovery actions and
credential admission checks must survive reconciliation.

The intervening integration changes concern auth presentation/configuration and
privacy work. Their model and API contracts remain unchanged here. This recovery
does not introduce a backend migration or a second financial model.

The later PR #853 lands primary-currency persistence. Its auth, session and
backend code is retained unchanged. The approved Preferences currency row now
reads that server-owned value and calls the existing setter. It shows save errors
and is disabled during a write. The separate old Profile layout is not restored.
PR #863 changes a canary fixture and has no native interface overlap.

The final one-way reconciliation at `0a512315142c8d59b71146b0e24e1848072634e2`
retains integration through `70b0cd3891937f026900aceb96ce5f556c76b0b3`.
The only new native file is the required-reason privacy manifest from #849.
Apple deletion admission, first-name initialization and personless analytics
work retain their backend owners and existing flag boundaries. There are no
changes to the recovered financial models, presentation, migration ownership
or native routes. Prior financial and interface evidence is retained. The
combined modularity budget passes. This is branch reconciliation, not an
integration merge or hosted migration.

## One presentation, existing record owners

| Surface | Shared presentation | Connected state and limits |
| --- | --- | --- |
| Navigation and Chat | `CuadraoAppShell`, `CuadraoChatCanvas` | Shared keyboard, voice, draft-return and temporary-chat interactions. Chat is explicitly a local development example; it does not call a provider or write financial records. |
| Receipt capture and review | Existing native capture, source viewer, review and saved receipts | DEBUG stores drafts per authenticated person on this device. Later, reopen and discard remain available. Posting, account selection and splitting are unavailable until their connected backend exists. |
| Home and Accounts | Existing Cuadrao Home layout, balance header, account and movement rows/details | `AccountsModel` and `FinancialLoopModel` retain real records and commands. |
| Expanded balance | Shared period controls, pager, balance readout and allocation | Exact current cash/assets/debt from the API. No invented historical curve. |
| Plan | Shared page, forecast/chart, cards, artwork, detail heading and disclosure | Existing Plan, Goal, Budget and Debt models retain amounts, warnings, histories and commands. The DEBUG scenario playground is an isolated example. |
| Household | Shared Home, account, Plan and Search presentation | Existing Household models retain membership, consent, permissions and recovery. |
| Search | Shared field, chips, filters, empty state and result rows | `FinancialSearchModel` owns real results and pagination. Unsupported Chat/Files searches show their unavailable state. |
| Profile | Shared grouped rows, avatar and destination presentation | Real identity and existing account actions. Unsupported DEBUG settings are identified as examples. Release gates remain. |
| Updates | Shared inbox and preferences return path | No synthetic notifications are presented as real. |

There is no balance-history endpoint in this slice. Current balances, future
scheduled points, and past balances are different records. The approved empty
history presentation remains until real historical data exists. Known zero is
still distinct from missing coverage.

## Appearance evidence

The `before` directory preserves captures from the retained approved app binary.
The `after` directory contains the same Preview routes rendered through the
extracted shared components. These are fixture comparisons, not proof of live
backend coverage. The connected journeys below provide that separate evidence.

The first comparison covers Home, Plan, Chat, Search and Profile in Spanish,
light and dark, plus expanded balance, Updates, Household and linked Plan detail in Spanish light.
[The comparison file](preview-comparison.json) records dimensions, comparison
regions, and unrounded differences. Ten of fourteen captures are pixel-identical
inside the comparison region. Home light, expanded balance, Updates and linked Plan detail have
small differences and are not described as exact matches. System status and
home-indicator regions are excluded.

| Example | Before | After |
| --- | --- | --- |
| Home | [Light](before/home-es-light.jpg) | [Light](after/home-es-light.jpg) |
| Chat | [Dark](before/chat-es-dark.jpg) | [Dark](after/chat-es-dark.jpg) |
| Plan | [Light](before/plan-es-light.jpg) | [Light](after/plan-es-light.jpg) |
| Linked Plan detail | [Light](before/plan-detail-es-light.jpg) | [Light](after/plan-detail-es-light.jpg) |
| Search | [Light](before/search-es-light.jpg) | [Light](after/search-es-light.jpg) |
| Profile | [Light](before/profile-es-light.jpg) | [Light](after/profile-es-light.jpg) |
| Household | [Light](before/household-es-light.jpg) | [Light](after/household-es-light.jpg) |

These first captures cover application source at `e6b7cf325`. Its later
accessibility identifier changes do not change those view layouts. The linked
Plan detail capture at `2f243fac2` preserves the approved layout. Its measured
mean absolute RGB difference is 0.00729 on the 0–255 scale, so it is not called
pixel-identical.

## Connected verification

The local API, Auth and Postgres use the isolated 59850 allocation with synthetic
identities and records. Provider keys are blank. The existing database was
restarted after its process stopped; it was not reset or reseeded. A generated
local invite secret enables Household verification without hosted credentials.

At `e6b7cf325`, four selected simulator journeys passed without skips:

- Chat keyboard, draft and example attachment survive a visit to Plan. Updates
  opens notification settings and returns. Recorded money stays unchanged.
- Profile uses the signed-in identity, opens the approved destinations, and
  changes appearance through the actual preference owner.
- The release-gate harness retains supported Profile settings and hides
  unsupported editing entries.
- Search edits an account, corrects a movement, edits an expected payment, and
  returns to its query and position. Spanish/light relaunch retains the result.

The first run also had three failures. Plan and recurrence could not find the
account picker because a DisclosureGroup identifier replaced its child
identifiers. Manual inspection confirmed the controls existed. The identifier
now belongs to the label. Its driver then needed a button-specific query because
the label and button both expose that identifier. Search's perspective test
tried to switch tabs from a pushed account detail; it now follows Back first.
The Search perspective rerun passed. At `f02ad86c9`, the recurring journey
passed, including Home's fixed 30-day window, explicit payment confirmation and
relaunch. The Plan card return and relaunch check also passed at that source.
Its old return control did not prove a native edge gesture; that distinction led
to the native navigation correction below.

The next run exposed two test setup errors. The Household check expected only
the HTTPS invitation format although this local API still returns the supported
legacy deep link. The failed check left Household selected for the following
personal-money tests. The invitation assertion accepts either supported format;
personal-account setup now selects Personal explicitly. Neither correction
changes the invite API or money records.

The receipt journey at `16ef25322` was interrupted after repeated XCTest
“App animations complete notification not received” waits following merchant
editing. This is not a passed check or a measured phone hitch. The screenshot
showed the edited merchant and saved draft. The focused journey now checks
capture, Later, original-source reopening, identity isolation and discard without
editing text. The pure store checks separately cover durable edits. The existing
[native acceptance issue #784](https://github.com/lagarcess/argus/issues/784)
retains the responsiveness investigation; this recovery does not close it.

The narrowed receipt journey subsequently passed capture, Later, original-source
reopening, unchanged money and isolation from the other local identity. Its final
discard step failed because the automation did not open the receipt options menu.
This remains an unresolved test failure, not a completed discard check. Changing
the confirmation selector did not address it. The next check observes the native
menu directly before any product change. Direct simulator interaction confirmed
that the menu, discard confirmation and return work. The driver now taps the
observed visible target; the product menu is unchanged.

The Household journey reached the shared-account correction but could not locate
Search's field. The failure hierarchy showed `screen.search` replacing the field's
own identifier. Accessibility containment at the screen owner preserves child
identities. This corrects the source of the failed query; it does not relax the
Household permission assertions.

The native return correction pushes Goal, Budget and Debt pages onto the stack
that opened them. Their existing models still own the saved route and financial
commands. Account and movement pages also use the system Back control. Focused
checks now exercise cancelled and completed edge swipes, nested activity,
relaunch and the original Home position. The navigation source review passed; the remaining linked-record journeys
are still running at this checkpoint. At `2064cb527`, the Home movement/account journey
passed both cancelled and completed Back gestures and retained the original Home
row position. The earlier native run stopped when a shared test helper still
requested the removed custom Back button. The shared helper now follows the
native control, retaining its legacy Foundation fallback. At `eda29ddaa`,
Plan card return and relaunch passed. Review then identified missing Plan data
for detail actions after cold restore. Direct simulator interaction reproduced
Record doing nothing. At `ac70fec02`, one native detail loader replaces three
detail-only tasks. It uses the existing Plan read to load the page and its action
data, with loading and retry. Its independent source review passed. The Goal
journey now checks allocation fields and the Record editor after relaunch.

[Connected captures](connected/manifest.json) retain screenshots from the passed
Chat, Profile, Search, Updates and recurring journeys, with each source revision.

The pure balance checks passed 20 connected cases and 82 existing history cases.
The application compiled, including test products. The shared modularity budget
passed after one-way reconciliation. Release compilation and signed Check3432
compilation passed at `0a512315142c8d59b71146b0e24e1848072634e2`. The signature,
bundle identity, build number and embedded privacy manifest were read back from
the actual app bundle. The build used the direct iPhone target with IDE indexing
disabled after Xcode's generic destination resolution failed. This affects the
local build command, not app source.

The local phone API was restarted from this reconciled source without resetting
its database or Auth. Existing synthetic sign-in, `/me` and financial-account
reads passed. Installation returned CoreDevice4016 because the physical phone
was unavailable. No installation or phone-acceptance claim is made. Three full
Budget, Debt and Goal journeys are running on the owned iOS26.5 fallback simulator.
[Build readback](check-3432-build.json) records the current delivery state.

## Review and delivery

The independent behavior review of the first full-shell checkpoint found no
actionable issue. The comment review removed two redundant narration comments.
Plan detail and receipt-draft changes received separate delta reviews.

The Plan detail delta through `40b2c45d0` received a clean independent review.
Receipt review through `16ef25322` found one unavailable location action. The
connected screen now reads the existing location availability rule and omits
that action. Preview still permits location requests. The same review found no
posting, identity-isolation or Release gate escape. Two redundant test comments
were removed. The 19 draft-only and 44 existing receipt checks passed.

The native navigation delta through `87b5b77f1` received a clean independent
source review. Its comment review removed one redundant narration line.
Reconciliation and the receipt/accessibility corrections through `8f37d127b`
received a separate clean review. The three currency session checks passed,
covering server truth across relaunch, refused writes, and unknown legacy values.
The test-navigation delta at `80e06c44f` also received a clean independent review.
Its simulator run is pending; source review is not a runtime pass.

At `80e06c44f`, the seven-journey run passed receipt capture, Later, source
reopening, identity isolation and discard. Plan return and cold restore also
passed, including opening the allocation fields and Record editor. Five checks
failed. Budget retained the correct record but lost its exact scroll position
after relaunch. Currency's identifier targeted a whole labelled row instead of
the actual menu. Debt and Goal menus opened, but the desired accounts were below
their virtualized rows. Household joined successfully and showed both members;
its test expected the leave control to exist before scrolling the long Form.

`63345b7ff` includes the focused corrections. The existing Plan routes own the
saved anchor and offset. The shared scroll helper reuses Search's offset math
with the intent of restoring recreated pages once. Its runtime acceptance is
still open. Native Back keeps the existing page position.
The currency label and native menu have separate accessibility elements. Test
drivers scroll the actual native collections without changing account matching,
money assertions, permission checks or the Budget position tolerance. The first
currency containment-only attempt did not fix the failure and is superseded by
the separate control. Independent source review through `63345b7ff` is clean.

Five new restoration model tests and six existing Search tests passed. The
existing Search selected-account preservation assertion failed in code unchanged
from integration. PR #839 records four pre-existing model failures; this is not
a clean full model-suite claim. In the affected simulator rerun, currency passed
and survived relaunch. Budget again failed the unchanged 12-point viewport
tolerance after returning from a contributor and relaunching. Its record totals,
correction and refund checks passed before that assertion. The final run executed five tests. Currency and the full Household journey
passed. The latter includes explicit sharing, view-only and edit permission,
correction, Search, Spanish relaunch and revocation. Budget failed its viewport
assertion. Debt and Goal reached the native options menu but their shared test
helper swiped down to reposition an already-visible option, dismissing the menu.
Their money assertions before that point passed. The helper now taps the native
menu item directly.

A retained Budget rerun at the same application source reproduced the drift.
Runtime geometry showed the saved first anchor stayed at 399.67 points. Each row
became 13.33 points taller because cold restore had not loaded AccountsModel.
Internal account IDs appeared in place of names and wrapped to another line.
The detail loader now loads the existing account owner as well as Plan before
showing Goal, Budget or Debt. Temporary tracing was removed. The focused test
checks unchanged row labels and position, then opens correction and Edit after
relaunch. This is a correction to the earlier diagnosis that attributed the
Budget failure to scroll state alone. Source review and pure tests did not
establish viewport restoration; simulator evidence takes precedence.

At `2f243fac2`, the retained Budget test passed (one executed, no failures or
skips). Account labels and row position survive cold relaunch; correction and
native Edit both open. A fresh independent review of the loader and test delta
found no actionable issue. Its comment review found no added or changed comments.
The same source was built for the test before this commit; the commit contains
that exact source diff.

Preview 3427 and Check 3431 were verified as separate installed apps before this
recovery. The delivery target is Check only. Preview's installed app, source and
fixture evidence remain the reference.

Lucas returned with the physical phone during verification. The trust and privacy
lane was informed that this lane owns the next Check install and review. The
phone was reachable initially, then became unavailable during installation.
An unlock/reconnect request is pending while simulator verification continues.

Automatic approval review previously rejected creation of a new draft PR.
No alternative PR-creation route has been used. Publication and device evidence
will be recorded only after those actions actually occur.
