# Argus Active Roadmap

Status: **ACTIVE — this is the execution board.** Opened 2026-08-06.

Supersedes the two short-lived next-cycle boards and the completed interim
roadmap. `docs/specs/private-alpha-next-roadmap.md` remains as P2 history and
contract reference, not as the active board.

## Why this board exists

A competitor review on 2026-08-06 ([driven.ai](https://driven.ai)) produced one
finding that reorders everything: Driven does not backtest, so it is not chasing
the same job. But its entire first session is a research read, and that is the
same first message Argus gets. Argus currently refuses it.

Users are lost at the first question, before reaching the thing Argus is
actually good at. That is the gap this board closes.

This is a timing change, not a thesis change. Argus stays the pre-flight
checklist: test the idea, see the evidence, remember why. It does not become an
investment command center, an agent marketplace, or a trading surface.

## Operating rules (founder-locked 2026-08-06)

1. **No phases, no incubation.** When a lane is dispatched it is built
   production-ready end to end: implementation, tests, evidence, docs, and
   user-facing polish in one lane. Review checkpoints are not a delivery model.
2. **Flags, not ceremony.** Work that is not ready for users ships behind a
   default-off flag on the same terms personalization memory did. The flag is
   the safety boundary; staged branches are not.
3. **Items 1 and 2 are serial with each other.** Both rewrite the same
   interpreter and confirmation-card surfaces, so they cannot run in parallel
   without fighting. Everything else runs concurrently behind flags.
4. **GitHub issues are secondary.** An open issue earns work when it serves a
   board item, blocks items 1 or 2, or the founder steers it in. Otherwise it
   waits. The board leads, the tracker follows.
5. **Non-overlapping file ownership.** Parallel lanes must not share spine
   files. Where they do, they serialize.
6. **Nothing merges on self-report.** Per-lane founder gate, exact-head
   evidence, browser proof for anything user-facing.

## The five

### 1. Answer the first question (serial, first)

Argus must handle an ordinary finance question without refusing it, then turn
the answer into something runnable.

- A factual or educational turn gets a real answer. No capability refusal, no
  confirmation-card interrogation, no unsupported-strategy rejection on what is
  obviously a knowledge question.
- A research read produces sources, freshness, and candidate entities, then
  offers one to three fully specified, runnable test cards. Tapping one opens
  the normal confirmation card. It never auto-runs.
- Suggestions are prebaked and backend-owned. The model may rank or explain
  closed candidates; it may not mint symbols, strategies, or asks. Every
  candidate passes resolver, asset-class, and coverage checks before it is
  tappable.
- Start with exactly two jobs: a single-company read, and a competitor
  comparison. No fundamentals suite, no screener, no valuation product, no
  skill store.
- Perplexity finance and web search modes are the likely provider; #377 is the
  open evaluation.

Absorbs stabilization items formerly ranked Tier 1 #1, #3, #4, and the
knowledge/statistics macro. The interpreter ValueError work is complete and
awaiting review; it removed the dead-end banner but the underlying refusal
remains, which is this item.

Simplicity bar: someone who knows nothing about investing must understand the
answer and the offered tests.

### 2. Master editing (serial, after 1)

The confirmation card carries exactly three actions: **Run backtest**,
**Change/edit assumptions**, **Cancel**.

- Change/edit assumptions is the only entry point to editing anything.
- Compound, multi-parameter edits must work in one turn. "Change this and add
  that" cannot silently drop half the request in any language. This is the
  largest known reliability gap in the existing loop.
- Capital and dates additionally get in-place editing that spends no turn: an
  elegant drawer on the confirmation card, in the spirit of how the profile
  monogram is edited in profile settings. This is in addition to the
  conversational path, never a replacement for it. On web the entry point is a
  small dedicated row, in the shape of "edit costs". On mobile it reuses the
  sheet primitive defined in the mobile spec, so both surfaces share one
  pattern rather than inventing two.
- **Consolidate the confirmation card from five actions to three.** Today it
  shows Run backtest, change dates, change assets, adjust assumptions, and
  Cancel. The end state is Run backtest, Change/edit assumptions, Cancel.

  **This is gated on multi-edit working, and must not ship before it.** Change
  dates and change assets are deterministic entry points that tell Argus
  exactly which field is being edited. Removing them routes every edit through
  the free-form conversational path, which is the path that currently drops
  compound edits. Consolidating first would remove the working escape hatches
  and leave only the broken one.

  Motivating case, observed in alpha testing 2026-08-06: a user tapped change
  dates, then broadened the request mid-sentence to include other changes while
  Argus was waiting on a single field. The lesson is subtler than "fewer
  buttons": even a scoped entry point must accept a broader edit gracefully
  rather than holding the user to the button they pressed.

Absorbs #335, the #141 macro, and the #237 umbrella.

### 3. Mobile PWA (parallel, behind flag)

The public exposure gate. Nothing ships publicly while phones are broken.

**Spec is written and founder-locked:**
[`2026-08-06-mobile-pwa-responsive-shell.md`](../superpowers/specs/2026-08-06-mobile-pwa-responsive-shell.md).
No implementation authorized yet.

Locked shape, in brief:

- Responsive by screen width, not device sniffing, on custom breakpoints
  matching DESIGN.md section 8 rather than Tailwind defaults.
- Two thresholds: below 1024px the dossier becomes an overlay sheet, below
  720px the full mobile treatment applies.
- The sidebar becomes an off-canvas drawer behind a `=` trigger. Web is
  unchanged.
- One sheet primitive at three heights serves the dossier, the discovery
  sources pane, and item 2's capital and dates editor.
- Delivery is responsive PWA polish. The native-shell and full-native options
  are closed, not deferred.
- Prerequisite found while speccing: `layout.tsx` references a manifest that
  does not exist, and there is no apple-touch-icon or theme-color, so
  home-screen install does not look app-like today.
- Desktop and laptop behavior must not regress; it is already strong.

### 4. Product memory (parallel, behind flag)

The differentiation competitors cannot copy, and it is still unproven in the
public product.

- Canonical Idea, IdeaVersion, EvidenceArtifact, and DecisionNote recall: A1b
  linked versions and A2 comparison.
- Comparing your own past strategies is the same engine as comparing
  competitors in item 1. Build them so they share it.
- Distinct from personalization memory. Product memory is canonical truth;
  personalization memory is an opt-in sidecar that may reference it and never
  becomes an alternate source of truth.

### 5. Sharing (parallel, behind flag)

Distribution, once there is something worth spreading.

- An immutable, sanitized evidence receipt. Not a shared chat transcript.
- Owner-created, owner-revocable, stripped of private runtime detail.
- Deliberately last of the five: sharing a broken loop spreads a bad
  impression.

## Continuous, not a lane

**Conversational runtime robustness.** Keep exercising the real chat runtime and
fixing what breaks. This runs alongside every lane rather than waiting its turn,
and it is how items 1 and 2 stay honest after they land.

Standing chore work, picked up alongside lanes rather than scheduled:

- **Extend the modularity budget to tests.** `.agent/modularity_budget.json`
  scans only `src` and `web`, and explicitly excludes `web/__tests__/**` and
  `web/e2e/**`. No Python test file is governed at all. The asymmetry is the
  problem: the interpreter lane had to extract a module to change production
  code by 13 lines, while a 2000-line test file lands with no friction. Six
  `tests/memory/` files now exceed 1000 lines, the largest bigger than the
  service it tests. Add `tests` as a scan root with baselines captured from
  current reality so it binds future work without a mass rewrite.
- **Strip the legacy Collections and Strategies code.** Dead ends and surfaces
  no longer exposed, plus any environment plumbing that only served them.
  Follow the onboarding strip-out pattern: remove the surface, keep legacy
  records read-safe, drop the env plumbing. **Not in scope:**
  `ARGUS_ASSET_PROVIDER_MODE`. An earlier draft listed it as a dead alias; it
  is live. It overrides `ARGUS_MARKET_DATA_PROVIDER_MODE` in
  `src/argus/domain/market_data/assets.py` so tests can pin the asset catalog
  independently of market data, and it is used by `tests/evals/` and
  `tests/agent_runtime/`. Leave it. It is worth documenting rather than
  removing, since a silent two-variable fallback chain is the same env-confound
  shape that has produced fake test failures before.
- **Implement the usage allowance meter colors.** `.agent/designs/argus/DESIGN.md`
  section 23 already specifies this completely and it was never built: teal
  at or above 30% remaining, `--rui-color-warning` above 10% and below 30%,
  and `--rui-color-danger` at or below 10% including exhaustion, with the
  lowest normalized active window governing. Color stays supporting information
  only, so the exact remaining count and truthful reset time must survive, with
  no pulsing or terminal-style treatment. Today `UsageModal.tsx` and
  `ProfileMenu.tsx` reference none of those tokens.

## Landed this cycle

- **Personalization memory** (PR #386) — complete loop behind a default-off flag
  scoped to `admin` and `developer` allowlist roles. Propose, confirm, inspect,
  explain, edit, delete, disable, reset, export, and temporary chat. Guests
  denied before any side effect.

  **Follow-up is specced and ready to dispatch, not pending decisions.** The
  recall loop is locked in
  [`2026-08-06-personalization-memory-recall-loop.md`](../superpowers/specs/2026-08-06-personalization-memory-recall-loop.md).
  Four Mem0 parameters
  are ratified: index-only over confirmed content, so Mem0 never sees
  unconfirmed material; storage on the existing Supabase database with no new
  datastore service; Mem0 as the OSS library running in-process inside the API
  service rather than the hosted platform; and its extraction, dedup, and
  conflict-resolution pipeline explicitly unused, because Argus owns extraction
  and the assisted-not-automatic rule forbids it.
- **Canary automation** (PR #385) — API-layer denial probe, deployed-SHA
  evidence binding, and the fix for the canary validating the wrong branch. A
  signup enumeration oracle and a false-evidence path were caught in review.
  Session injection for the browser golden path remains open on #383.
- **Retest current-data windows** (PR #363, in review) — the waste guard moved
  out of the chat turn into the dossier button, computed before any click.

## Deliberately not doing

From the competitor review: no agent marketplace, no model picker, no
multi-hundred-API integration story, no autonomous monitoring, no portfolio
system, no messaging channels, no trading workflow, and no auth-gated marketing
site standing between a visitor and their first test. Guest entry stays the
activation path, because a completed first backtest is activation, not account
creation.

## Secondary tracker state

Open issues serve the board or wait. Currently aligned: #377 (item 1), #335 /
#237 (item 2), #332, #367, #369, #365, #364 (robustness). Currently waiting:
#294, #244, #350, #236, #314, #376, #378, #383.
