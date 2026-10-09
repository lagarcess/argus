# Cuadrao marketing website lane: handoff

Lane parent: [#880](https://github.com/lagarcess/argus/issues/880) (children #887 to #892). Written 2026-10-09 when the lane was paused so the founder can reserve Claude usage for the Consumer lane. Everything a successor needs is in the Git repository and the linked GitHub records. No private notes, session scratchpad or conversation is required.

This document is the single pickup point. It links to the canonical contracts and evidence instead of copying them; if this page and a linked source disagree, the linked source wins.

## 0. Read this first

**The successor's immediate scope is website aesthetics, worked with the founder, while Cuadrao LLC formation is pending.** Nothing is authorized to publish.

**First action:** ask the founder which aesthetic tweaks they want. Resume the existing touch-up branch and worktree recorded below. Do not restart from integration or discard the current work. Do not start anything listed under "Held" in section 1.

**The founder may change Business positioning after an interview with José.** Do not rewrite the website's promise, headlines or story from that interview or in anticipation of it. Visual work (spacing, type scale, color use, imagery, motion, layout polish) is in scope; changing what the Business site claims or who it speaks to is not, until the founder brings the outcome.

## Touch-up ownership checkpoint, 2026-10-09

The founder assigned this Codex chat ownership of Marketing only. This checkpoint
supersedes the earlier fresh-branch instruction. Business and Consumer worktrees,
code, and services are outside this assignment.

**The founder has not accepted the current design.** Prior passing tests and
review reports do not establish design approval. The first question was sent to
the founder asking what to change and what to keep. The founder later requested the screenshot removal and footer correction recorded below. Whole-page design acceptance remains pending.
New copy remains a draft in the [copy review](../reports/evidence/cuadrao-marketing-touchup/copy-review.md).

Verified at 13:54 America/Chicago on 2026-10-09:

- [PR #939](https://github.com/lagarcess/argus/pull/939) is open and draft, targeting `codex/private-alpha-next`.
- Branch `codex/marketing-touchup-delivery` is checked out at `/Users/garces/.codex/worktrees/cuadrao-marketing-delivery/private-alpha-next`.
- Local HEAD and GitHub PR head both equal `e09ee0e35b3c92546cf86c47f83b2fdbf10b47af`. The worktree was clean before these documentation updates.
- The original integration base is `bbf4da23f01296af4ac639386fe9a0960218a49f`. No fetch, reconciliation, reset, or rebase was performed during pickup.
- Updated preview `http://127.0.0.1:4512/` returns HTTP 200. Its existing process runs from this worktree's `marketing/` directory.
- Original comparison `http://127.0.0.1:4511/` returns HTTP 200. Its existing process runs from `/Users/garces/.codex/visualizations/2026/09/26/01a0de75-29ee-71f0-8f58-0d2bb3934a33/cuadrao-marketing-touchup/canonical/marketing`.
- Neither preview was restarted or changed. Preserve the comparison files and process.

The [touch-up evidence](../reports/evidence/cuadrao-marketing-touchup/README.md)
records the prior implementation and verification. Its screenshot manifest pins
`85c8cdf2a17c4a8dc6ff2990b75d6d44451cc40e`. The only subsequent change under
`marketing/` is test synchronization in `e2e/touchup.spec.ts`. Prior browser logs
record 142 passing checks and six repeated footer checks. Those suites were not
rerun during pickup, and no new visual acceptance or CI verdict is claimed.

The repository-wide pstack checkpoint points to the older connected-preview lane,
not this touch-up. Use this handoff, PR #939, and its committed evidence to continue.
No private transcript is required.

Next, record the founder's requested changes here before implementing them in
`marketing/`. Keep new copy Spanish first for founder review. Use the isolated test
ports in the evidence README so tests do not displace either comparison preview.
Read the mandatory product and technical documents before code changes.

No merge, publication, hosted change, real email, or public-form activation is
authorized. Existing LLC, operator wording, and provider holds still apply.

## Founder follow-up, 2026-10-09

The founder requested removal of the Business product screenshot because the product is incomplete and the numbers are incorrect. The Marketing-only change removes its whole section, related copy and styles, and the served image. Historical source captures remain in the evidence folder. See the [touch-up correction record](../reports/evidence/cuadrao-marketing-touchup/README.md#founder-correction-2026-10-09).

The founder confirmed the footer should rest at the cropped Cuadrao wordmark with photos fully hidden. Extra downward scrolling reveals a short photo peek, and release returns to the crop. The local Marketing implementation now removes autoplay, the grid and pause control, keeps normal page height and native upward/keyboard navigation, and disables peeking for reduced motion. Typecheck and lint pass. The rebuilt preview passes 20 focused browser checks. Fresh screenshots are committed under `docs/reports/evidence/cuadrao-marketing-touchup/footer-peek-screens/`; prior footer checks describe the removed animation.

The founder supplied the replacement footer photos. The unchanged dressmaker PNG is on the left and the unchanged artisan JPG on the right, with native dimensions and CSS upper-body cropping. Original files and the main editorial photos are preserved. The crop was inspected locally; final design acceptance remains open. The [footer correction record](../reports/evidence/cuadrao-marketing-touchup/README.md#footer-correction-2026-10-09) owns implementation details and remaining verification. The capture script writes new evidence to `footer-peek-screens/` without replacing historical captures. No Business or Consumer runtime, services, forms, or original comparison files were changed.

### Header and drag refinement request, 2026-10-09

The founder approved changing the navigation label to **Cómo funciona** and separating the language controls visually from main navigation. The English counterpart is **How it works**. The founder also requested less footer drag resistance and asked for inspection of Granola first. The release captain visited [Granola](https://www.granola.ai/) and exercised its footer: extra scrolling readily revealed a shallow photo band, then the footer returned when input stopped. This is an interaction reference, not permission to copy its assets.

The bounded Marketing implementation groups ES/EN separately and uses one localized navigation label for desktop and mobile. Footer input accumulates without losing movement between frames; touch holds the peek until release. Photos still hide fully at rest. Local build, browser checks, and refreshed evidence are being completed. Existing release holds remain unchanged.

## 1. Scope and decisions

### Status

| Item | Approved | Implemented | Verified | Pending |
| --- | --- | --- | --- | --- |
| Independent website package `marketing/` (Next.js, Bun, own lockfile) | yes | yes, on integration | CI, browser suite, local review | none |
| Business inquiry form (Resend) | yes | yes | mock providers only (unit, browser); **no real email has been sent** | hosted receipt test (held) |
| Personal early-access signup (Supabase) | yes | yes | mock and local real PostgREST/Postgres (see evidence) | production migration and hosted test (held) |
| Operator tools: `marketing/scripts/signups.ts`, `marketing/scripts/verify-origin.ts` | yes | yes | unit tests, local runs | first hosted use (held) |
| Privacy notice (Spanish and English) | wording approved 2026-10-08 as a draft, then three corrections | yes | review, CI, browser | **publication held** |
| "Lean, calm" mark, favicon, Apple icon, brand artwork | approved 2026-10-08 | yes | review, CI | none |
| Website-only promotion to `main` (Option B) | opening approved, **merging not approved** | draft PR #927 | CI, release-gate review | founder approval |
| Production migration `20260920000000` | no | repo file only | applier digest computed, never run against a hosted database | held |
| Render service `cuadrao-marketing` | no | not created | no Render state ever read | held |
| Domain cutover, indexing, Search Console | no | no | n/a | held |

### The founder's permissions and holds (as stated, 2026-10-07 to 2026-10-09)

Done under explicit permission: merging #895, #903, #923, #906 and #926 into integration (each once final head CI was green, a review was complete and no blocker was open); opening #927 as a draft under Option B; read-only inspection of Cloudflare and Resend; creating the `notify.cuadrao.ai` domain in Resend with tracking off and adding its DNS records (the founder added the DKIM record by hand and a scoped Cloudflare token for the other three).

Held, each needing its own explicit yes naming the exact object:
- **Cuadrao LLC and the operator wording.** Formation is pending. The privacy notice has no operator section on purpose and names no individual. The prepared "Cuadrao LLC" wording is in the [runbook](../runbooks/cuadrao-marketing-launch.md) ("Operator wording (prepared, not published)") and must stay unpublished until the founder confirms the company is formed and operates the site.
- **Public contact and signup forms** stay unpublished for the same reason.
- **#929 and #927 merges.** The founder merges #929; the successor must not merge it, or #927, to simplify anything.
- **The production migration, the paid Render service (about $7 per month), provider secrets, hosted emails, the domain cutover, indexing and Search Console.**
- **Integration merges never authorize promotion to `main`, deployment, migrations, emails or publication.**
- This handoff PR is not to be merged without the founder's approval.

### What the successor must not infer or start

- Approval of wording is per string. The founder approved the privacy text and the Contact under-form line (the same correction, applied in #926). They did not approve other new strings individually; confirm new or changed copy with the founder, Spanish first. Keep the Contact under-form line consistent with the privacy page (a unit test guards the Contact line).
- Do not publish, announce, index, create a Render service, enter or request secrets in chat, send any email to a real address, run the migration applier, or change DNS. Do not treat a green CI or a merged PR as permission for any of these.
- Do not redraw the mark or approximate the wordmark. Sources and hashes: section 4.
- Do not touch the iOS app or consumer files; the Consumer lane owns native use of the brand assets.
- Do not clean up Git history that contains the founder's name (the founder said none is needed).
- Do not use hosted facts in section 4 as current; they are dated observations.

## 2. Exact work state

Measured 2026-10-09 with `git fetch origin`.

| Ref | SHA |
| --- | --- |
| `origin/codex/private-alpha-next` (integration) | `5d9a1f55aa03a56a1b8e3afb064f4b4c70e25aec` (this handoff PR is cut from it) |
| `origin/main` | `a9286b21886eb03df7a21f2f4b7d5e79af570679` (144 commits and 35 migrations behind integration) |

### Pull requests

| PR | State | Head / merge SHA | Notes |
| --- | --- | --- | --- |
| [#895](https://github.com/lagarcess/argus/pull/895) website package and forms | merged | `fbb6bb447` (head `d0447a7da`) | landing on [#880](https://github.com/lagarcess/argus/issues/880#issuecomment-6049488390) |
| [#903](https://github.com/lagarcess/argus/pull/903) origin verifier, claim-then-send notices | merged | `1ffb53548` (head `32ad2c207`) | |
| [#923](https://github.com/lagarcess/argus/pull/923) notice-run stop and review notes | merged | `a9a30b37d` (head `37c68ea81`) | carried the #903 landing record |
| [#906](https://github.com/lagarcess/argus/pull/906) privacy rewrite, "Lean, calm" mark, brand artwork | merged | `b5e440c48` (head `5fd4de67c`) | landing: [PR comment](https://github.com/lagarcess/argus/pull/906#issuecomment-6069299602), [#880](https://github.com/lagarcess/argus/issues/880#issuecomment-6069299930) |
| [#926](https://github.com/lagarcess/argus/pull/926) Contact line says "to reply", not "only" | merged | `5d9a1f55a` (head `22a0b5d70`) | review and landing on the PR and [#880](https://github.com/lagarcess/argus/issues/880#issuecomment-6071016567) |
| [#929](https://github.com/lagarcess/argus/pull/929) recapture evidence, fix two revert notes | **open**, base integration | head `f555e53267b71bc36417fbbbabad9c2c636d1ff9` | scope below; founder merges |
| [#927](https://github.com/lagarcess/argus/pull/927) website-only promotion to `main` | **open draft**, base `main` | head `2d44044e405a4eae37d1c22567a5c3137ff53b7f` | not authorized to merge |

**#929's actual scope.** Documentation and evidence images only; no code. The final review of #927 found that the evidence folder's privacy and contact screenshots still showed text that #906 and #926 replaced, including the withdrawn privacy wording that named an individual. `capture.mjs` was rerun against a fresh production build at integration `5d9a1f55a`. Changed: eight screenshots (`es-privacy`, `en-privacy`, `es-contact`, `en-contact` at 1440 and 390 pixels) plus `webkit-en-contact-390.jpg`, `browser.json`, one row in the [evidence README](../reports/evidence/cuadrao-marketing-launch/README.md) (it now names the commit), and two revert notes (`marketing/README.md` and the runbook now say that on `main`, reverting the promotion commit removes `marketing/` and its migration file and nothing else). Home and Personal captures are byte-identical to before. 13 files; CI 18 of 18 green (one earlier install failure was the registry flake described in section 3, cleared by a rerun).

### Dependencies and merge order

1. **#929 merges into integration first** (founder). Then the candidate #927 equals integration on every path it carries.
2. **#927 merges only on the founder's explicit approval to promote**, after the pre-merge confirmations in section 5.
3. The migration, Render service, secrets, tests and cutover follow the order in the held deployment request: [deployment request](https://github.com/lagarcess/argus/issues/880#issuecomment-6069169773) (steps 0 to 5) and [held migration and Render requests](https://github.com/lagarcess/argus/issues/880#issuecomment-6069364033).

### Deployment candidate and its refresh procedure (#927)

Branch `codex/cuadrao-marketing-main-promotion-prep` is cut from `origin/main` (`a9286b218`). At head `2d44044e4` it carries **142 files: 140 new, 2 modified, 0 deleted** (`git diff --name-status origin/main...HEAD`). Carried: `marketing/**`, `supabase/migrations/20260920000000_cuadrao_early_access_signups.sql` (SHA-256 `ea2a2a010d31f1c05222561d5f90fa024df2fac46a466107c7bdf3138d11aad0`), `tests/test_cuadrao_early_access_postgres.py`, the [launch record](../reports/2026-10-07-cuadrao-marketing-launch.md), the [runbook](../runbooks/cuadrao-marketing-launch.md), the [forms contract](../specs/cuadrao-marketing-forms-contract.md) and the [evidence folder](../reports/evidence/cuadrao-marketing-launch/README.md). The two modified files, `.github/workflows/ci.yml` (a `marketing-checks` job and its entry in the aggregate `ci` job's `needs`) and `tests/test_ci_workflow.py`, are written for `main`'s simpler workflow and are **not** mirrored from integration. `web/`, `src/`, `ios/`, `render.yaml` and every other migration are byte-identical to `main`.

Refresh once after any change lands on a carried path:

```bash
# in the candidate worktree, on codex/cuadrao-marketing-main-promotion-prep
git fetch origin
SRC=<integration commit that contains the accepted change>
git checkout $SRC -- marketing \
  docs/reports/2026-10-07-cuadrao-marketing-launch.md \
  docs/runbooks/cuadrao-marketing-launch.md \
  docs/specs/cuadrao-marketing-forms-contract.md \
  docs/reports/evidence/cuadrao-marketing-launch \
  supabase/migrations/20260920000000_cuadrao_early_access_signups.sql \
  tests/test_cuadrao_early_access_postgres.py
# remove carried files that no longer exist upstream
for d in marketing docs/reports/evidence/cuadrao-marketing-launch; do
  comm -23 <(git ls-files $d | sort) <(git ls-tree -r --name-only $SRC $d | sort)
done | xargs -r git rm -q -f
git diff --stat $SRC HEAD -- <the same paths>   # must be empty after the commit
git commit -m "feat(marketing): refresh the candidate to <SRC>" && git push
```

A push to a `codex/**` branch runs full CI. Then update the body of #927 (heads, counts) and confirm `git diff --name-status origin/main...HEAD` is still 140 added, 2 modified, 0 deleted and that `web/`, `src/`, `ios/`, `render.yaml` are unchanged.

### Branches and local state

| Branch | Role | State |
| --- | --- | --- |
| `codex/cuadrao-marketing-main-promotion-prep` | candidate for #927 | pushed, head `2d44044e4` |
| `codex/cuadrao-evidence-refresh` | #929 | pushed, head `f555e5326` |
| `codex/cuadrao-marketing-handoff` | this document | pushed with this PR |
| merged and no longer needed: `codex/cuadrao-marketing-launch`, `codex/cuadrao-marketing-website-ops`, `codex/cuadrao-privacy-icloud-wording`, `codex/cuadrao-contact-line-consistency`, `codex/cuadrao-903-landing` | merged branches | left in place, no cleanup |

**Uncommitted or local-only work: none.** Every worktree this lane used was clean when it stopped. Local worktrees (convenience only, not required): `argus-worktrees/cuadrao-marketing-main-prep`, `cuadrao-landing` (#929), `cuadrao-privacy`, `cuadrao-903-review` (detached review checkout), `cuadrao-marketing-launch`, `cuadrao-handoff`. The session's own worktree has an untracked `probes/` directory that predates this lane and belongs to the native-auth proof work, not to this lane; do not touch it.

### Issues

#880, #881, #882, #887, #888, #889, #890, #891 are open (#892 is deferred). Their acceptance is not closed because hosted acceptance, publication and cutover have not happened. Do not close them from the repository state alone.

## 3. Verification

Each result names the commit it covers. "Browser" means the Playwright suite (desktop and mobile projects, with the automated accessibility checks) against a **fresh** production build. Every figure was observed on a clean checkout of that commit unless stated.

| Commit / PR | Unit | Typecheck, lint | Browser | CI (GitHub) |
| --- | --- | --- | --- | --- |
| `32ad2c207` (#903) | 132 pass (review) | clean | 85 and 86 verifier checks, local, both modes | all green |
| `37c68ea81` (#923) | 135 pass | clean | verifier 87 (candidate mode) and 88 (public mode) checks, 0 failed, wrong mode rejected (exit 1), local | 18 of 18 |
| `5fd4de67c` (#906) | 175 pass | clean | 130 of 130 at `cc8fb0e9d`, fresh build; screenshots rebuilt at `5fd4de67c` | 18 of 18 |
| `22a0b5d70` (#926) | 177 pass | clean | 130 of 130, fresh build | 18 of 18 |
| `f555e5326` (#929) | no code change | n/a | recapture ran on a fresh build at `5d9a1f55a` | 18 of 18 after rerunning an install flake: [run](https://github.com/lagarcess/argus/actions/runs/37859719987) |
| `2d44044e4` (#927 candidate) | in CI | in CI | in CI (177 unit, 130 browser) | push run green: [run](https://github.com/lagarcess/argus/actions/runs/37859748948) (frontend, backend, guest-release-gates, marketing, ownership, aggregate `ci`) |

Evidence files: the [evidence README](../reports/evidence/cuadrao-marketing-launch/README.md) names each file and the commit it vouches for ([storage proof](../reports/evidence/cuadrao-marketing-launch/storage-proof.md), [verify-origin local run](../reports/evidence/cuadrao-marketing-launch/verify-origin-local.json), [browser report](../reports/evidence/cuadrao-marketing-launch/browser.json), [screens](../reports/evidence/cuadrao-marketing-launch/screens)). The verifier's local run was repeated after the redirect-host change at `61294c3c2`; the file records the counts.

### Reviews and what was done about them

Independent reviews were run by separate agents; their full text is not in the repository, so their findings and dispositions are recorded here and in the landing records.

| Subject (head) | Verdict | Findings and disposition |
| --- | --- | --- |
| #903 (`32ad2c207`) | clean | Four non-blocking findings (a provider outage could claim every row; hand-send advice assumed one run; failed-release path untested; evidence counts) and doc nits. All settled in #923. |
| #923 (`61294c3c2`, `5698c7776`) | clean, twice | Non-blocking: the release-failed advice could lead to a second email; stop message for test sends; a missing test; evidence attribution. Fixed at `5698c7776` and `37c68ea81`. |
| #906 (`acf1b180a`, `cc8fb0e9d`, `5fd4de67c`) | one blocking each at the first two heads, clean at `5fd4de67c` | Blocking: "only to reply" was inaccurate because the contact email also keys an in-memory submission limit; then the limiter's sweep ran only on submission, so the "at most two hours" statement could be false on a quiet site. Fixed by a timer sweep and by the three approved wording corrections. Also fixed: malformed `favicon.ico` header, wrong kerning and ink numbers in the brand README, test gaps. Not changed, by choice: every brand SVG names its gradients `a`, `b`, `c` (use them as image files, never two inline; documented in the brand README) so the approved hashes stay stable. |
| #926 | clean (proportionate, by the lane's author, posted on the PR) | A sweep of every "solo" and "only" in the site copy found no other exclusive data-use claim except the Personal line, which review confirmed accurate. |
| #927 (`056998035`) | clean | Non-blocking: main's aggregate `ci` is skipped, not failed, when a needed job fails (pre-existing on `main`); stale evidence (fixed in #929); two false revert notes (fixed in #929); dated statements become false at merge. Comment on the [PR](https://github.com/lagarcess/argus/pull/927#issuecomment-6071091669). |

### Reproduce the relevant checks

Prerequisites: Node 24.21.0 (the pin in the [runbook](../runbooks/cuadrao-marketing-launch.md)), Bun 1.3.14 (`ARGUS_CI_BUN_VERSION` in `.github/workflows/ci.yml`; a lockfile written by another Bun version is unreadable in CI, regenerate with `npx -y bun@1.3.14 install`), and Playwright Chromium (`npx playwright install chromium`).

```bash
cd marketing
npx -y bun@1.3.14 install --frozen-lockfile
bun test __tests__
bun run typecheck
bun run lint
bun run build                      # required: Playwright serves an existing build and otherwise tests a stale site
CI=1 npx playwright test           # starts the mock providers (4510) and the site (4511, 4512)
```

- Free the ports first and kill stale `next-server` and `mock-providers` processes; orphans cause cross-run interference. Run Playwright with `CI=1` and write to a log; piping it can hang.
- Read-only origin check (from `marketing/`): `bun run scripts/verify-origin.ts <origin> [--public --www <origin>]` (GET only; candidate mode expects noindex, `--public` expects indexable).
- Evidence recapture: `bunx next start -p 4511` then `node ../docs/reports/evidence/cuadrao-marketing-launch/capture.mjs http://127.0.0.1:4511 <commit>` from `marketing/`.
- Brand regeneration (only if the mark or wordmark changes, which needs the founder): `python3 scripts/make-brand-assets.py` (needs `fonttools`, `brotli`, `uharfbuzz`) and `node scripts/make-icons.mjs`. Tests keep every brand file's geometry identical.
- Main-shaped workflow test (candidate only): `pytest tests/test_ci_workflow.py` from the repository root with the repo's Python environment (38 passed with `tests/test_private_alpha_canary_split.py` in the final review).

Environment-variable names the tests and the site use (values are never committed): `RESEND_API_KEY`, `RESEND_API_URL`, `CUADRAO_INQUIRY_FROM`, `CUADRAO_INQUIRY_TO`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `CUADRAO_SITE_INDEXING`, `CUADRAO_TRUSTED_CLIENT_IP_HEADER`, `CUADRAO_NOTICE_FROM` (operator notice script), `NODE_VERSION`, `NEXT_TELEMETRY_DISABLED`. The Playwright config injects test values pointing at the local mock; see [`marketing/.env.example`](../../marketing/.env.example) and the [forms contract](../specs/cuadrao-marketing-forms-contract.md).

Local preview that cannot send real email: start `node marketing/e2e/mock-providers.mjs`, then run `next start` from `marketing/` with the Resend and Supabase variables above pointing at `http://127.0.0.1:4510` and a throwaway key and recipient. Submissions land in the mock.

### Known failures and unresolved findings

- **CI install flake.** An install step sometimes fails with "Fail extracting tarball for next" (a registry error, not code). Rerun the failed jobs after the run has finished.
- **`main`'s aggregate `ci` job** is skipped, not failed, when a job it needs fails, and a skipped required check counts as passing. Pre-existing on `main`; whoever merges #927 must read every job, not only `ci`. Integration's workflow already has the stricter form.
- **Stale sentence in the launch record:** "Its own landing is recorded below once it merges" (about #906) is out of date; the landing is on #906 and #880. Fix it the next time the record changes. Dated statements ("nothing was promoted to `main`", `main`'s newest migration) become false when #927 merges; update them in the post-merge record.
- The Business footer and founder story show the founder's name and LinkedIn by the founder's instruction. The privacy notice names no operator or individual.
- No unresolved blocking finding is open on any PR in this lane.

## 4. Operational context

### Brand sources (approved 2026-10-08, "Lean, calm")

Pinned and hashed in the [pinned comment on #906](https://github.com/lagarcess/argus/pull/906#issuecomment-6066490040). Files: [`marketing/app/icon.svg`](../../marketing/app/icon.svg) (tiled; iOS icon and favicon), [`marketing/brand/`](../../marketing/brand/README.md) (mark without tile in light and dark, outlined wordmark in two colors, light and dark lockups, with the specification, geometry and colors in `brand/README.md`). The wordmark is the website's own: Space Grotesk 700, letter-spacing -0.085em (not the lighter variant shown on early icon sheets). The shared design guide that the Consumer lane records native use in is [`.agent/designs/cuadrao/DESIGN.md`](../../.agent/designs/cuadrao/DESIGN.md) ("Brand identity"). `marketing/app/apple-icon.png` (180 px) is web-only; never enlarge it. No dark or tinted iOS icon variants exist.

### Services, connectors and credentials

| System | Use | Access | Where an authorized operator supplies credentials |
| --- | --- | --- | --- |
| GitHub (`gh`) | PRs, CI, issue records | authenticated CLI | operator's own login |
| Resend | `notify.cuadrao.ai` sending | connector available | the sending key (restricted to `notify.cuadrao.ai`) is created and typed by the founder into Render; never in chat, commits, logs or evidence |
| Cloudflare | zone `cuadrao.ai` DNS | connector available; a scoped day-long token was used once and deleted by the founder | cutover would need a new scoped token created by the founder |
| Supabase (free plan) | Personal signup table | connector listed as connected but the project-level server rejected its credentials (HTTP 401) when last checked 2026-10-09 | `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` typed by the founder into Render and the operator's shell; the production connection string for the applier is held by the founder |
| Render | the website service | **connector returned "unauthorized" on 2026-10-08/09**; the CLI token was expired on 2026-10-07; no Render state has ever been read by this lane | the founder reconnects the Render connector in Claude's Settings, Connectors; a project-level `render` server uses its own API key, replaced from the Render dashboard |
| iCloud Mail | `hola@cuadrao.ai` custom-domain mailbox | the founder's account | the founder |

### Hosted facts, with when and how they were observed (do not treat as current)

- **Resend `notify.cuadrao.ai`:** domain created, region `us-east-1`, tracking off; reported **Verified** with four records. Recorded 2026-10-08 in the [launch record](../reports/2026-10-07-cuadrao-marketing-launch.md), read through the Resend connector. Not reread since.
- **Cloudflare zone `cuadrao.ai`:** 9 records before and 12 after the three records were added; 0 of the 9 existing records changed (iCloud MX and SPF, Apple domain TXT, `sig1` DKIM CNAME, Resend root records). Recorded 2026-10-08 from a Cloudflare API readback in the launch record. No DMARC record exists as of that date. Never add Cloudflare Email Routing: it would replace the iCloud MX.
- **Supabase GitHub integration:** disabled by the founder on 2026-10-08. Verified **by behavior** (no preview branch appeared on three migration PRs; a probe commit showed no Supabase check), not by reading the dashboard setting, which is dashboard-only. The #927 release review asked for a dashboard confirmation before merging.
- **Production migration ledger:** read-only observation on 2026-10-07 (81 entries; production's newest equals `main`'s newest, `20260914120000`, but the ledgers differ); recorded in the [runbook](../runbooks/cuadrao-marketing-launch.md). It will have changed if the consumer lane applied anything since.
- **Render:** nothing observed.
- **Production Supabase project reference** `lgdhvepyrzbnscqssgqq` is the one named by Supabase's own PR notices on 2026-10-07; the founder confirms it when issuing an approval record.

### Migration applier (the consumer lane's tool)

`scripts/ops/apply_approved_migrations.py` applies an explicit version list and refuses hosted hosts unless a committed approval record names them; `scripts/ops/production_migration_gate.py` is the read-only gate. The run digest for `["20260920000000"]` is `090e86fa74fb104a0d3984653624cf72fd65faa8ac7bb2a930ed937c73fb0f8f` (computed locally, never run against a hosted database). The signup migration must precede the consumer's 35 files because the applier records versions as a strict prefix. Full packet and prerequisites: the [held request](https://github.com/lagarcess/argus/issues/880#issuecomment-6069364033). `supabase db push` is never used.

## 5. Next steps

**What the successor can do now (no approval beyond the founder's direction in conversation):**

1. Ask the founder for the aesthetic tweaks. Resume `codex/marketing-touchup-delivery` in the existing worktree recorded in the ownership checkpoint.
2. For each requested tweak, update `marketing/` on the existing branch and verify the affected behavior. Use the isolated test ports in the touch-up evidence README. Continue PR #939. Record any founder-authorized landing on the PR and #880. Integration remains protected.
3. Keep new or changed user-facing words Spanish first and confirmed with the founder. Keep the Contact line and the privacy page consistent.
4. After a tweak lands on a path #927 carries, refresh the candidate once (section 2) and update #927's body.
5. Do not change product copy that expresses Business positioning until the founder reports the José interview outcome.

**What requires the founder's approval (each its own explicit yes):**

1. Merge #929 (founder merges), then promotion (#927) under the pre-merge confirmations: the Supabase GitHub integration really off in the dashboard; the auto-deploy setting of the `argus-backtests` service (not in `render.yaml`); every CI job read, not only `ci`.
2. Confirm Cuadrao LLC is formed and operates the site; then publish the operator wording and the forms.
3. Apply `20260920000000` (founder runs the gate, backup and applier; consumer lane's tool).
4. Create the Render service (phase 3a without provider secrets, later 3b) and reconnect the Render connector if a read is needed.
5. Provider secrets, two founder-supplied test addresses, hosted tests, then cutover, indexing and Search Console.
6. Merge this handoff PR.

## 6. Canonical sources and optional material

Canonical, not copied here: the [launch record](../reports/2026-10-07-cuadrao-marketing-launch.md), [runbook](../runbooks/cuadrao-marketing-launch.md), [forms contract](../specs/cuadrao-marketing-forms-contract.md), [package README](../../marketing/README.md), [brand README](../../marketing/brand/README.md), [evidence](../reports/evidence/cuadrao-marketing-launch/README.md), [shared design guide](../../.agent/designs/cuadrao/DESIGN.md), and on #880 the [deployment request](https://github.com/lagarcess/argus/issues/880#issuecomment-6069169773), the [held migration and Render requests](https://github.com/lagarcess/argus/issues/880#issuecomment-6069364033) and the [checkpoint comment](https://github.com/lagarcess/argus/issues/880#issuecomment-6073256570).

Optional, not needed to resume, and not committed: the working session's scratchpad held icon exploration sheets (rounds of mark variations and the finalists sheet, as images and HTML), screenshots of the local site, a one-off Cloudflare record script that read a scoped token from a local `.env` (the founder deleted the token), and review mutation scratch copies. The approved artwork and every hash needed to resume are in the repository and on #906; losing the scratchpad loses nothing required.

### Current local verification

The screenshot removal and footer peek pass a fresh production build and 20 focused browser checks. The hidden photo-loading failure found during the first run is fixed. See the touch-up evidence README for the result and photo provenance. Both implementation agents returned ownership and stopped. Only the updated Marketing preview on 4512 was rebuilt and restarted. The original comparison remains on 4511. Header feedback is advisory; no header changes were requested or made. No merge, push, publication, provider activation, or hosted change occurred.

The final runtime source is `f98974687caecc01c24786007e448754a782d1a2`. Its fresh screenshot manifest pins that exact source. Later evidence-only changes preserve the runtime bytes. The local changes remain unpushed while the founder reviews the design.
