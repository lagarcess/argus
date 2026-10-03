# Cuadrao release UI checkpoint

UI handoff, October 2, 2026. This checkpoint implements the founder's 17-item
presentation scope and the subsequent avatar correction. It does not establish
external TestFlight readiness or connected service acceptance.

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

- iPhone 18 Pro simulator, iOS 27. No physical-phone installation in this checkpoint.
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

## Integration and review disposition

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
  physical-phone test or external TestFlight submission was performed.
- GitHub CI status belongs to the PR. This is a UI handoff, not a READY report.

The [main execution board](../../../specs/argus-execution-board.md#cuadrao-release-ui-landing-order)
owns remaining delivery work. The [design guide](../../../../.agent/designs/cuadrao/DESIGN.md)
owns stable patterns and the visually inspected Mobbin references.
