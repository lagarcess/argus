# Web composition refinement

The previous READY claim is withdrawn. This checkpoint compares the preview
with the existing Argus web application and records a bounded refinement in
the same PR. It is not founder visual acceptance or landing authorization.

## Refined preview and comparison

The [after run](after/browser-run.txt) passes all **46 cases**, with **48 PNGs**
and one interaction record per case. All records name code head
`53029f5d7c18827adba9daf79197936086ea0188` and report zero API/external requests
and zero browser exceptions. The [verification record](after/verification.json)
also records the full web tree, environment and the other local gates.

| Surface | Before/reference | Refined preview |
| --- | --- | --- |
| Desktop starting chat | [Existing web](reference-bound/integration-1440-cold-chat-expanded-rail.png), [before](before/preview-before-1440-argus.png) | [Centered greeting and composer](after/desktop-en-light-argus.png) |
| Desktop active chat | [Existing web](reference-bound/integration-1440-active-chat-fixture.png) | [Stable header and docked composer](after/desktop-en-light-active-chat-docked.png), [200% text and independent scrolling](after/desktop-en-light-active-chat-text-200-scroll.png) |
| Home | [Desktop before](before/preview-before-1440-home.png), [narrow before](before/preview-before-390-home.png) | [Desktop](after/desktop-en-light-home.png), [Spanish/Dark](after/desktop-es-dark-home.png), [narrow Coming up priority](after/narrow-home-upcoming-priority.png) |
| Tablet navigation | [Existing collapsed rail](reference-bound/integration-834-cold-chat-collapsed-rail.png), [before](before/preview-before-834-argus.png) | [Collapsed rail with Accounts](after/tablet-es-light-accounts.png), [local rail choice across preferences](after/tablet-es-light-rail-preferences-local-state.png) |
| Account inspection | Earlier preview used dialogs at every width | [Accounts side pane](after/accounts-desktop-account-inspector.png), [Search side pane](after/search-desktop-account-inspector.png), [selected URL after resize](after/tablet-account-inspector-stacked-after-resize.png), [fresh tablet sheet](after/tablet-account-detail-after-resize.png) |
| Settings | [Existing web](reference-bound/integration-1440-settings-open.png), [before](before/preview-before-1440-settings.png) | [Desktop grouped rows](after/desktop-en-light-settings.png), [narrow Spanish/Dark](after/narrow-es-dark-settings.png), [System persistence](after/settings-spanish-system-dark-persistence.png) |
| Narrow reading area | [Before starting chat](before/preview-before-390-argus.png) | [Starting chat](after/narrow-en-light-argus.png), [active chat at 200% text](after/narrow-en-light-active-chat-text-200-scroll.png), [360px long label](after/compact-es-light-enlarged-text-long-label.png) |
| Fixture truth and recovery | Same approved local sample boundaries | [Guest handoff](after/desktop-en-light-guest-registration-handoff.png), [unsaved draft](after/account-create-unsaved-review.png), [correction review](after/account-correction-review.png), [empty](after/home-empty-state.png), [loading](after/home-loading-state.png), [error](after/home-error-state.png) |

Desktop/tablet composition follows the existing web owners. The five-destination
narrow navigation keeps the mobile identity and participates in shell layout,
so its actual height reserves the reading area. A selected account URL keeps
its same nonmodal detail on resize; new tablet/narrow opens use the existing
sheet. No shared production component, token or backend contract changed.

Additional proof: [5 production checks](after/production-run.txt),
[2,205 frontend tests](after/unit-run.txt), [build/TypeScript](after/build-run.txt),
[lint](after/lint-run.txt) and [combined-tree modularity](after/modularity-run.txt).
Lint reports eight existing shared-component warnings and no errors. The first
full run at `f2eacef6` found narrow navigation covering an account action; that
incomplete run is excluded. All after captures were refreshed after the fix.

Environment: Chromium 147.0.7727.15, Node 26.10.0, macOS 27 arm64, local Next.js
development route, reduced motion and America/Santo_Domingo timezone. Each PNG
has adjacent metadata with dimensions, language, theme, time and source SHA.
Starting greeting text may vary with the existing guest greeting's local time.
Capture-only masking hides the Next.js development indicator. Real auth,
server authorization, financial persistence, physical devices and other browser
engines are not exercised. The production not-found result may use HTTP 200
streaming with an explicit Next.js 404 marker; it contains no preview markup.

The final PR audit must revalidate the accepted application and test inputs,
account for the reference-only correction below, and state the terminal
CI/review outcome. Technical proof does not grant founder visual acceptance.

## Reference-server provenance revalidation

Review identified that the earlier harness verified source files while relying
on externally started servers. At `8e5d74e25bb3e26952019823ab386cdb7153b075`,
one manifest now owns each source root, loopback origin, readiness route and
Next.js command. Playwright starts and stops all three servers with existing
server reuse disabled. A source directory and a browser origin can no longer
silently refer to independent processes.

The [negative check](reference-bound/occupied-port-rejection.json) placed an
unrelated HTTP 200 listener on a reference origin. Playwright refused it before
running a case or accepting a screenshot; the [failure log](reference-bound/occupied-port-run.txt)
records the expected refusal. The subsequent [reference run](reference-bound/run.txt)
passed all **nine cells**, captured **31 PNGs**, and recorded zero network
violations, page exceptions or console errors. Each cell records the owned
server configuration, checked source hashes and capture SHA. The current
preview also verifies its complete route file set. All temporary servers were
stopped by framework teardown; the user preview on port 3197 was untouched.

These captures supersede the original reference run's provenance. The original
before images remain historical. Useful replacements:
[production desktop](reference-bound/production-source-1440-cold-chat-expanded-rail.png),
[integration tablet](reference-bound/integration-834-cold-chat-collapsed-rail.png),
[current desktop guest preview](reference-bound/preview-current-1440-argus.png).
The [verification record](reference-bound/verification.json) records exact
source identity and limitations.

The correction changes only the reference gate, its configuration and its
shared manifest. Product source and the 46-case acceptance inputs remain
identical to the after capture head. Their application tree is
`ecedb7edac3f5973703573781d19781718141ed9`. That acceptance remains valid; the
new reference harness and its affected capture gate were reverified instead.
The corrected full web tree is `56941cbf59ef3a2e7fbecbed1c30b0c7100c333a`.

To repeat this reference gate, first extract each manifest revision's `web`
tree into that entry's isolated source directory and link its `node_modules`
to the installed workspace dependencies. Do not copy environment files.
For `preview-current`, extract the current worker HEAD. Leave the three
manifest ports free, then run from `web` with a fresh evidence directory:

```sh
ARGUS_PREVIEW_EVIDENCE_DIR=/absolute/path/to/docs/reports/evidence/new-run \
  bunx playwright test --config e2e/ecosystem-preview-reference.playwright.config.ts
```

Focused lint and harness TypeScript checks pass. A plain repository-wide
`tsc --noEmit` separately reports existing Bun-test declaration and unrelated
e2e typing failures; no files responsible for those failures changed here.

## Before and web references

The [reference run](before/run.txt) passed all nine cells and captured 31 PNGs
at code/harness head `2da77b1a09769901b9ca9bfe28d317eddde2ffa1`. Each cell's JSON
records source hashes, environment, requests and capture identity. All nine
record zero network violations, page exceptions and console errors. This is
the historical run; use the enforced server-ownership captures above for
current reference provenance.

| Surface | Existing web | Preview before refinement |
| --- | --- | --- |
| Desktop starting chat | [Production source](before/production-source-1440-cold-chat-expanded-rail.png), [integration](before/integration-1440-cold-chat-expanded-rail.png) | [Preview](before/preview-before-1440-argus.png) |
| Tablet navigation | [Expanded](before/integration-834-cold-chat-expanded-rail.png), [collapsed](before/integration-834-cold-chat-collapsed-rail.png) | [Preview](before/preview-before-834-argus.png) |
| Desktop active chat | [Production source](before/production-source-1440-active-chat-fixture.png), [integration](before/integration-1440-active-chat-fixture.png) | Historical sample-chat proof remains in the [original evidence index](../README.md) |
| Desktop settings | [Existing web](before/integration-1440-settings-open.png) | [Preview](before/preview-before-1440-settings.png) |
| Home composition | New ecosystem surface; use web shell and density, mobile content hierarchy | [Desktop](before/preview-before-1440-home.png), [tablet](before/preview-before-834-home.png), [narrow](before/preview-before-390-home.png) |
| Narrow chat/settings | [Chat](before/integration-390-cold-chat.png), [settings](before/integration-390-settings-open.png) | [Chat](before/preview-before-390-argus.png), [settings](before/preview-before-390-settings.png) |

Production-source identity: `a9286b21886eb03df7a21f2f4b7d5e79af570679` from an
isolated temporary source extraction. Integration identity:
`c3b2042b9b69c5b75e173d145ed0020f00ccd79e`. Named rendered source owners are
byte-verified against those Git objects. The full source web tree is recorded
for context, not claimed as a live deployment verification.

Both reference apps run with mock authentication and browser-fulfilled API
fixtures. They do not establish authorization or server persistence. All
unrecognized API/external traffic is rejected before transmission. Only local
Next.js development HMR sockets are allowed; an initial attempt that blocked
those sockets could not hydrate the webpack reference and was corrected before
this accepted run. No model turn, provider request or real financial write ran.

The reference harness freezes animations/caret and hides development-only
chrome through the repository's existing `FREEZE_CSS`. The preview's visible
sample disclosures remain. Captures use Chromium, 1440/834/390 × 1000, English,
Light, reduced motion and the America/Santo_Domingo timezone. Broader language,
theme, text-size and interaction acceptance belongs to the after run.

The [inheritance map](../../../ecosystem-web-preview.md#web-inheritance-checkpoint)
and [spec refinement](../../../../superpowers/specs/2026-09-28-responsive-ecosystem-preview.md#september-28-refinement-checkpoint)
define the changes. Earlier screenshots remain unchanged as historical evidence.
