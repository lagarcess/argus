# Private Alpha Interim Roadmap

Status: **ACTIVE — founder-outcome and live-QA execution source**

Original roadmap date: 2026-07-16

Last reconciled: 2026-07-27

Current stable integration checkpoint: `codex/private-alpha-next` at
`75e87206574cca41a715d357b366bda569beb8bd`.

That checkpoint contains the founder-accepted outcome baselines delivered
through independently revertible vertical slices:

- adaptive result-chart range switching from PR #264 at `0c0d481`;
- account recovery and session controls from PR #261 at `a639566`;
- truthful Usage allowances and accounting from PR #259 at `2eb6874`;
- executable capability truth from PR #266, with final candidate `e10bdd2` and
  integration merge `bbd1d2b`; and
- the Always Progresses continuity baseline from PR #268 at `847c413`; and
- the default-on grounded-discovery baseline from PR #276, candidate
  `cc8b5563`, merged as `c212107a`.

The checkpoint also contains the bounded calendar-materiality correction from
PR #267 at `d6d1134` and the environment-documentation checkpoint at
`b7fd6f08`. Since that checkpoint, integration also received the chat-header
title/owner-menu correction from PR #274 at `291b58f7`, removal of the explicit
private-alpha onboarding product from PR #275 at `88ae8c77`, and truthful stale
Run settlement from PR #277 at `2d5a2b52`. Supported strategy transitions
through confirmation then landed from PR #278 at `b80d95a2`.
Modeled-cost preservation landed from PR #280 at `d16f7496`, followed by the
Guest experience from PR #279 at `53e812e9` and chat next-move presentation
from PR #281 at `8fde4ac1`. PR #282 then made ordinary backend tests
provider-free and added the alpha API suites to CI at `059f8e82`; PR #286 made
the complete backend `tests/` directory the required CI gate at `75e87206`.
Those two CI landings improve verification truth without changing product
behavior.

Frozen archaeological reference: `claude/argus-alpha-audit-c2d919` at
`f1d03a1d847628e6a8d681b22337ad5fc6c5ebfd`. It is retained for exact historical
comparison only, not as an active donor or implementation base for the remaining
outcomes.

Last promoted `main` checkpoint: functional promotion merge `5d1eec11`, with
the [production-promotion record](https://github.com/lagarcess/argus/blob/main/docs/release-manifests/2026-07-14-main-production-promotion.md)
completed on `main` at `217ead12`.

This is the bounded pivot between the latest `main` promotion and the remaining
P2 compounding loop in
[`private-alpha-next-roadmap.md`](private-alpha-next-roadmap.md). Existing
issues #228 through #253 are supporting evidence and possible implementation
material, not the roadmap itself. #213 remains excluded.

The roadmap does not authorize implementation by itself. The founder selects a
user outcome. A fresh vertical slice then proves that outcome against the
latest integration checkpoint.

## Authoritative Founder Outcomes

These six outcomes are the interim roadmap:

1. **Argus always progresses.** A conversation never becomes trapped in a
   semantic loop, repeated recovery, unexplained terminal state, or
   deterministic cul-de-sac. Every accepted turn makes meaningful progress or
   gives the user a clear, actionable stopping point.
2. **Security and usage are unlocked for users.** Users can reach account
   security and session controls and can see truthful usage, remaining
   allowance, what counts, and when it resets.
3. **Graphs have range switching.** Users can change the visible result range
   without changing the approved backtest, corrupting the effective data
   window, or seeing frontend-invented facts.
4. **Argus knows what it can and cannot do.** It distinguishes supported,
   unsupported, and not-yet-supported requests without overpromising and helps
   the user reach a supported next step.
5. **Discovery is grounded and Argus can suggest.** Search and suggestions are
   source-backed, provider-validated where required, and limited to actions
   Argus can actually support.
6. **Omnisearch lives up to its full capability.** Omnisearch provides useful
   unified retrieval and navigation across the user's Argus artifacts, with
   truthful previews and actionable results.

### Current Completion Ledger

This ledger records accepted user-visible behavior, not issue activity or a
deterministic test result by itself.

| Founder outcome | State | Completion evidence |
| --- | --- | --- |
| 1. Argus always progresses | **Baseline delivered; standing quality bar** | PR #268 delivered bounded semantic progress, durable ordinary-turn recovery, exact-once Run reconciliation, stale-authority rejection, fact-preserving refinement, concrete trajectory adapters, EN/ES browser proof, one authorized real Run, and reload-stable result truth. Reviewed head `5585c6a` landed on integration as `847c413b`. Later reproduced defects receive bounded follow-ups; they do not reopen an unbounded search for every possible conversational edge case. |
| 2. Security and usage are unlocked | **Complete** | #248/PR #261 delivered reachable recovery, password, and current/other/all-session controls with real Supabase Auth QA. #247/PR #259 delivered reachable Settings -> Usage, backend-owned hourly/daily message and simulation truth, exact reset instants, durable exactly-once accounting, EN/ES desktop/mobile behavior, and exact-head real-auth/local-persistence QA. |
| 3. Graphs have range switching | **Complete** | #250/PR #264 delivered adaptive presets, Custom/Reset, daily/intraday presentation, EN/ES desktop/mobile browser proof, reload-to-ALL, immutable full-run truth, and zero range-interaction network calls. |
| 4. Argus knows what it can and cannot do | **Complete** | #241/PR #266 proved supported golden-cross execution, fail-closed momentum-breakout and news-sentiment recovery, the general future-performance boundary, compatible fact preservation, explicit supported-alternative selection, localized Quick take, and exact-head founder-visible browser QA. Candidate `e10bdd2` landed as `bbd1d2b`. |
| 5. Discovery is grounded and Argus can suggest | **Baseline landed default-on; deployment closure open** | #244/PR #276 delivered typed explicit discovery, bounded source-backed Search, provider-resolved candidates across supported asset classes, persisted EN/ES discovery UI, honest kill-switch recovery, provider accounting, review, browser QA, and locked eval cases. Candidate `cc8b5563` landed as `c212107a`; integration policy now treats the flag as a default-on emergency kill switch. PR #281 then landed the presentation (`8fde4ac1`) and PR #287 the selection identity plus a ticker-collision correction (`ea2b3f35`). #244 remains open: comparison phrasing reliability, the recorded exposure-vehicle limitation, plus Render configuration and exact-SHA canary evidence are required before tester exposure. |
| 6. Omnisearch lives up to its full capability | Not yet accepted complete | No founder-accepted slice yet proves the full Omnisearch journey end to end on the current checkpoint. |

Outcomes 2, 3, and 4 must not be redispatched unless a new regression is
reproduced. Outcome 5's merged baseline must not be duplicated; its open work
is limited to the recorded pre-activation gates. Outcome 1 is a standing
quality bar applied to each later slice: fix a reproduced violation at its
owner, but do not redispatch a broad, open-ended continuity program. Existing
evidence remains the regression baseline.

The bounded [Always Progresses closure evidence](../reports/always-progresses-closure-evidence.md)
remains valid. The
[same-conversation stress audit](../reports/2026-07-25-always-progresses-post-merge-stress-audit.md)
and [guest post-integration runtime observation](../reports/2026-07-25-guest-post-integration-runtime-regression.md)
record later signals without assigning unproven causality or authorizing a
broad repair lane.

### Continuity Follow-up Ownership Queues

These issues are bounded follow-ups to reproduced post-merge findings. They do
not reopen the completed Always Progresses baseline as one broad runtime
program.

The three ownership queues may run independently when their files and
canonical owners remain distinct. Issues **within one queue execute serially**
in the order below. After an issue lands, the next issue starts from the
updated integration checkpoint rather than stacking unreviewed worker branches.
This is shared-owner serialization, not a native GitHub `blocked-by` graph.

#### Runtime reliability

1. [#269 — Diagnose ordinary starter failures at the call ceiling](https://github.com/lagarcess/argus/issues/269)
   is **classified, fixed, and landed with Guest PR #279 at `53e812e9`**.
   The seven receipts covered two Guest requests rather than one exhausted
   turn. Guest terminal settlement failed while serializing the
   `guest_session` allowance; Guest commit `5adff1f4` owns the correction.
   Integration runtime policy, the seven-call allowance, provider routing, and
   fallback accounting were exonerated. Issue #269 is closed; this does not
   justify another runtime lane.

This queue is no longer an implementation queue. Guest public exposure remains
separately gated by the launch-safety register below. Do not open a second #269
runtime lane.

#### Protected interpreter/edit spine

Execute serially:

1. [#270 — Preserve supported strategy transitions through confirmation](https://github.com/lagarcess/argus/issues/270)
   is **complete**. PR #278 landed as `b80d95a2`; its eight acceptance criteria
   were reconciled and #270 is closed.
2. [#271 — Preserve modeled costs across asset edits](https://github.com/lagarcess/argus/issues/271).
   PR #280 landed as `d16f7496` after proving cost preservation, evidence-owned
   natural-language and card edits, explicit zero, date/asset edits, launch
   agreement, and reload. The issue stays open only for its named integrated
   preservation repetition.
3. [#272 — Recover without re-asking facts the conversation owns](https://github.com/lagarcess/argus/issues/272).
   This is now the next protected interpreter/edit-spine issue and must start
   from `75e87206` or a later clean integration checkpoint.

Only one agent owns the interpreter/edit spine at a time. Do not combine these
issues into another open-ended continuity rewrite.

#### Artifact lifecycle and presentation

Execute serially:

1. [#273 — Settle stale Run rejection to the latest usable artifact](https://github.com/lagarcess/argus/issues/273)
   is **complete**. PR #277 landed as `2d5a2b52`; all eight acceptance criteria
   were reconciled and #273 is closed.
2. [#249 — Restore result and recovery surface ownership](https://github.com/lagarcess/argus/issues/249)
   is now ready to start from `75e87206` or later. Guest has landed, so the
   overlapping chat-shell and recovery-presentation owner is stable.

Issue #249 was updated instead of duplicating presentation ownership. It
records:

- `TRY NEXT` / `WHAT HAPPENED` leakage on generic recovery;
- compact recovery parity between ownership paths;
- malformed option presentation; and
- Quick take quality drift as an observation, not yet a separate regression or
  blocker.

[Coordination issue #237](https://github.com/lagarcess/argus/issues/237)
records all three queues. Lineage notes on #238, #239, and #242 preserve the
relationship to delivered work without reopening those completed boundaries.
Each correction still requires exact-head browser QA and integration
reverification before its issue can close.

### Next Ownership Handoffs

This is the current dispatch gate, not another speculative backlog:

| Ownership lane | Current owner | Next handoff |
| --- | --- | --- |
| Runtime reliability | #269 correction landed inside Guest PR #279 at `53e812e9`; #269 is closed | No runtime lane remains. |
| Protected interpreter/edit spine | #271 implementation landed through PR #280 at `d16f7496` | Run its focused integrated closure journey, then close #271. #272 must use `75e87206` or later. |
| Artifact lifecycle and presentation | Guest PR #279 landed at `53e812e9` and released the shared shell owner | Start #249 from `75e87206` or later. |
| Grounded discovery | PR #276 landed as `c212107a`; chat next-moves polish PR #281 landed as `8fde4ac1`; integration default is on and #244 remains open | Do not duplicate the implementation. Before tester exposure, close the recorded comparison-routing gap, configure Render, and prove the exact deployed SHA/canary. |
| Chat next-move presentation | PR #281 landed as `8fde4ac1` (stacked rows, sources panel, shared in-flight lock); PR #287 landed as `ea2b3f35` (Slice D: discovery selection carries the resolver's identity, plus a resolution-corroboration fix) | Slice D is closed — the chosen-state marker was cut deliberately, and carry-forward on switch was deferred out of the lane as general interpreter work. Only Slice B remains in `docs/superpowers/specs/2026-07-26-chat-next-moves-live-progress-polish.md` (live progress lines, blocked on three backend prerequisites). New work must start from `ea2b3f35` or later. |
| Discovery candidate resolution | PR #287 corrected a ticker-collision defect: a resolved candidate must now corroborate the entity the sources named, so a gold miner is no longer offered for a Tron question | Known limitation accepted and recorded in `docs/superpowers/specs/2026-07-25-grounded-discovery-search-v1-design.md` §5.1: crypto-exposure ETFs are dropped alongside true collisions because the two are structurally indistinguishable to a token check. Surfacing exposure vehicles deliberately is real product value and needs its own design. Owned by #244. |
| Guest grounded discovery | Specified, not started — `docs/superpowers/specs/2026-07-27-guest-grounded-discovery-quota.md` | Meter the guest ask per session; do not gate the candidate tap. Supersedes the "registered users only" line in the grounded discovery design. Allowance number is founder-owned. |
| Full Omnisearch | The accepted grounded-discovery contract is now on integration | Reconcile the existing Omnisearch owner onto `75e87206` or later; do not invent discovery truth or activate Search implicitly. |

The next bounded continuity lanes are #272 and #249. They have different owners
and may proceed in parallel, but work inside each ownership queue remains
serialized.

### Guest Main-Promotion And Public-Exposure Register

Guest code is integrated, not deployed or publicly exposed. The checked-in
product defaults are `ARGUS_GUEST_ACCESS_ENABLED=true` and
`NEXT_PUBLIC_GUEST_ACCESS_ENABLED=true`, with explicit `false` as rollback.
`ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED=false` remains the separate permanent
account gate.

Before promotion to `main` or any internet-facing Guest traffic, the release
captain must:

1. validate the exact promotion SHA on the branch-deployed staging/private-alpha
   surface and retain the canary evidence;
2. configure hosted Supabase anonymous Auth and server-validated Turnstile,
   including `NEXT_PUBLIC_ARGUS_TURNSTILE_SITE_KEY`;
3. prove trusted-origin/client-IP handling, the Guest bootstrap limiter, owner
   isolation, replay safety, and global capacity rejection;
4. set a hard provider spending limit and record the accepted daily budget,
   first traffic cohort, monitoring owner, and alert destination;
5. schedule bounded Guest cleanup with an accountable owner and prove dry-run,
   deletion, converted-account protection, and failure alerting;
6. complete the release manifest and obtain founder go/no-go approval.

The authoritative operational checklist is
[`docs/GUEST_PUBLIC_LAUNCH_SAFETY.md`](../GUEST_PUBLIC_LAUNCH_SAFETY.md).
Execution commands and rollback order live in
[`docs/PRIVATE_LAUNCH_RUNBOOK.md`](../PRIVATE_LAUNCH_RUNBOOK.md), and the
promotion record uses
[`docs/release-manifests/TEMPLATE.md`](../release-manifests/TEMPLATE.md).

## Product Relationships, Not An Issue Order

```mermaid
flowchart LR
    LIVE["Argus always progresses — baseline delivered / standing bar"]
    ACCESS["Security and usage unlocked — complete"]
    RANGE["Graph range switching — complete"]
    TRUTH["Capability truth — complete"]
    DISCOVERY["Grounded discovery and suggestions"]
    OMNI["Full Omnisearch capability"]

    LIVE -. "applies to every conversational slice" .-> TRUTH
    LIVE -. "applies to every conversational slice" .-> DISCOVERY
    LIVE -. "applies to every conversational slice" .-> OMNI
    TRUTH --> DISCOVERY --> OMNI
```

Capability truth is a product prerequisite for grounded suggestions. Grounded
discovery is a product prerequisite for complete Omnisearch. Progress behavior
applies across all conversational work. This relationship does not prescribe
an issue order or require one giant implementation lane.

## Vertical-Slice Delivery Contract

For each founder-selected outcome:

1. name one complete user-visible journey and its expected behavior;
2. reproduce that journey on the latest stable integration checkpoint;
3. branch from that checkpoint and change only what the journey requires;
4. salvage donor code only when a specific hunk remains correct and useful;
5. run focused deterministic checks and production-parity local browser QA,
   including persistence and reload where the journey uses them;
6. compare the candidate with the integration baseline and reject regressions;
7. present the working behavior to the founder or private-alpha users before
   promotion;
8. record the exact candidate and merge SHAs, rollback boundary, and any later
   tester-exposure gates.

An issue can provide evidence or requirements. It is not the unit of completion
unless the selected slice explicitly makes it so.

### Live QA Is Required Before Merge

Deterministic tests prove contracts; they do not prove the product experience.
Every vertical slice requires live QA proportional to its surface:

- auth, history, and UI work uses real auth and verifies interaction,
  persistence, navigation, and reload where applicable;
- conversational runtime work uses real prompts and inspects the visible
  response, hidden typed state, recovery, and reload;
- backtest work completes the relevant approval, execution, result, and reload
  journey with real provider data;
- contract work starts the production-parity API and compares the generated
  contract before browser smoke.

An exact deployed canary is a later tester-exposure gate when the founder is
preparing a candidate for users. It does not replace slice-local QA.

### Guardrail Ratchet

Keep the minimum guardrails required for security, privacy, correct accounting,
durable state, grounded evidence, and duplicate-execution prevention. Do not
add speculative strictness that blocks the Golden Path. Tighten further in
response to observed user or operational evidence.

## Source Order

Every implementation owner reads, in order:

1. `AGENTS.md`
2. `docs/PRODUCT.md`
3. `docs/ARCHITECTURE.md`
4. `docs/API_CONTRACT.md`
5. `docs/DATA_MODEL.md`
6. `.agent/designs/argus/DESIGN.md`
7. this roadmap
8. the founder-selected vertical-slice brief
9. related issues as supporting evidence
10. relevant sections of `docs/specs/private-alpha-next-decision-memo.md`
11. release references only when the slice touches release evidence

Canon wins if sources conflict. The selected slice owns its journey, allowed
surfaces, no-touch areas, and acceptance evidence.

## Checkpoint And Salvage Discipline

The integration branch is the stable working checkpoint. Known corner cases do
not invalidate it or authorize unrelated scope expansion.

The audit donor records useful experiments and failure evidence, but it is not
an integration candidate. Never merge it wholesale. For each selected slice:

1. create a fresh branch from the latest integration SHA;
2. map donor code to the selected user journey;
3. reuse only dependency-clean commits or the smallest justified hunks;
4. prove the complete journey and relevant regressions;
5. merge one reviewed, revertible slice into integration;
6. update this checkpoint before selecting another slice.

Parallel investigation is allowed on genuinely independent surfaces. Shared
runtime, API, database, and web-shell changes integrate one owner at a time.

## Current Remaining Outcomes

The founder chooses among the remaining outcomes; this table is not an
implementation queue.

| Outcome | Product proof still required |
| --- | --- |
| Grounded discovery and suggestions | The default-on baseline is merged, and its presentation landed with PR #281 — candidates read as stacked rows carrying their verified reason, with a sources panel. Before tester exposure, prove reliable comparison phrasing, decide the guest allowance, configure Render, and pass the exact-SHA canary; keep #244 open until then. |
| Full Omnisearch | Owner-scoped conversations, results, decisions, and evidence are retrievable with truthful previews and useful navigation. |

Do not select the next slice from the archived issue dependency graph. Select
it by user value, regression risk, and the smallest complete live journey.

### Completed slice: Capability truth

Status: **COMPLETE — PR #266 merged as `bbd1d2b`; issue #241 closed**

The completed vertical-slice contract is archived at
[`2026-07-22-capability-truth-executable-boundary-design.md`](../archive/2026-07-22-capability-truth-executable-boundary-design.md).
The original path remains as a compatibility pointer for existing issue and PR
links. [Issue #241](https://github.com/lagarcess/argus/issues/241) and
[PR #266](https://github.com/lagarcess/argus/pull/266) contain the detailed
implementation and review evidence.

This is acceptance and narrow gap-closing for the founder outcome, not a rebuild
of the completed P2.1 registry work.

The slice proves four end-to-end classes: a supported golden-cross control, a
recognized but non-executable momentum-breakout request, an unsupported external
news-sentiment rule, and the general future-performance boundary. The last class
applies to any asset, strategy, amount, language, or future horizon. Argus says
it cannot predict future performance and separately offers a supported
historical test. Only an explicit user choice creates the historical draft;
compatible asset and capital facts carry forward, while a future horizon never
silently becomes a historical date range.

This slice adds no forecasting engine, Search/discovery behavior, strategy,
indicator, provider, or second capability registry. If exact-head reproduction
is already correct, align tests and evidence only rather than manufacturing a
runtime change.

Completion evidence:

- deterministic runtime, registry, mocked-eval, frontend, modularity, and CI
  gates passed on the candidate family;
- the sanctioned interpreter suite passed 27/27 at `497e2b8`;
- the final bounded correction passed independent review and exact-head
  founder-visible browser QA at `e10bdd2`;
- supported golden cross reached the ordinary confirmation/result path;
- momentum breakout, news sentiment, and future-performance requests remained
  non-executable and useful, with compatible facts preserved;
- an explicit supported alternative plus historical period produced the correct
  confirmation without carrying stale unsupported identity; and
- the founder approved merge, PR #266 landed as `bbd1d2b`, and issue #241
  closed as completed.

### Completed slice: Argus always progresses

Status: **BASELINE DELIVERED — PR #268 merged as `847c413b`; standing quality
bar remains active**

This pillar protects every later conversational surface.
The founder-approved end-to-end contract is
[`2026-07-23-always-progresses-continuity-design.md`](../superpowers/specs/2026-07-23-always-progresses-continuity-design.md).
The serialized execution plan is
[`2026-07-23-always-progresses-continuity.md`](../superpowers/plans/2026-07-23-always-progresses-continuity.md).
Together they require every accepted operation to advance typed state or reach
a clear, actionable stopping point across clarification, confirmation, Run,
result, retry, and reload.

Completion evidence:

- one turn-wide deadline, model-call allowance, semantic progress assessment,
  and first-wins internal terminal;
- durable accepted-turn lifecycle with owner-scoped reconciliation, adjacent
  Retry, supersession, and reload projection;
- server-owned response-option Retry and Run-action identity with exact replay,
  collision rejection, and no duplicate job, Run, action bubble, usage charge,
  or result;
- founder-visible production-parity journeys for clarification, edited
  confirmation, one real Run, ambiguous transport, ordinary failure and Retry,
  stale authority, no-progress recovery, result refinement, Spanish recovery,
  and reload;
- disposable-Postgres lifecycle/RLS/accounting proof, concrete runtime
  trajectory adapters, the zero-provider browser harness, the sanctioned
  interpreter scorecard, independent review, and exact-head CI; and
- reviewed PR head `5585c6a` merged into `codex/private-alpha-next` as
  `847c413b`, with byte-equivalent trees.

This completion does not claim deployment or tester exposure. #228, #233, and
#237 retain those release-owned gates. Narrow issue-specific follow-ups also
remain open where their own acceptance exceeds this founder outcome, including
#239's dedicated trajectory cleanup, #243's combined release gate, and #251's
remaining period-truth work.

## Retained Product Decisions

### Usage allowance (#247 — complete)

- Alpha uses backend-owned UTC calendar windows: messages are limited to 60
  per hour and 200 per day; simulations are limited to 10 per hour and 50 per
  day. These are operating limits, not pricing.
- The authenticated read contract returns both windows, exact `period_end`,
  and backend-derived `available_now` and limiting-window truth.
- Count one message only when an accepted turn reaches a durable substantive
  terminal product outcome. Malformed, unauthenticated, duplicate-replay,
  abandoned, and infrastructure-failed turns count zero.
- Count one simulation at first successful unique durable admission. Replays
  and pre-admission rejections count zero. A later execution failure does not
  erase the admitted unit.
- Chat and direct launches share the accounting rule.
- The frontend localizes backend reset instants and never derives quota truth.
- Billing, plans, credits, provider/model tokens, and internal CostLedger data
  remain out of scope.

Before tester exposure, the target environment must receive migrations through
`20260722000004`, enable `ARGUS_BACKTEST_JOBS_SHADOW_ENABLED=true`, and pass an
exact-SHA canary. Those are exposure gates, not reasons to reopen #247 or block
its integration completion.

The pre-existing stale direct-job GET reconciliation gap remains tracked by
#231; #230 owns any atomic database primitive it requires. It is not part of
the completed user-visible Usage slice.

### Incomplete data windows (#251)

- Implementation checkpoint (2026-07-25): coverage preflight now persists a
  code-owned `adjustment_reason`, distinguishes exchange-calendar alignment
  from provider-driven truncation, and emits the existing period-adjustment
  sidecar only for provider-driven changes. The reason is measurement-visible
  without changing normalized confirmation action identity.
- Fit to provider-supported data only when a viable common window remains; a
  material fit must not be silent.
- Ordinary weekend or holiday session normalization inside available coverage
  shows no warning.
- A material head or tail correction is explained in provider-neutral language
  immediately before the confirmation card. Preserve the LLM-authored voice
  through stream and reload; deterministic localized copy is degraded fallback.
- The card shows effective dates while requested dates remain durable
  provenance.
- Preflight consumes no simulation unit.
- If no viable common window exists, return typed recovery and no runnable card.
- The approved effective window remains identical across result facts, chart,
  prose, evidence, reload, replay, and Omnisearch.
- Remaining follow-ups: preserve normal LLM-authored adjustment voice through
  stream and reload, and decide whether historical cards without the typed
  reason need notice backfill. Neither follow-up is implemented by this slice.

## Historical Planning Archive

The former eight-pillar taxonomy, issue dependency map, Wave 0 sequencing,
shared-surface matrix, quick-win analysis, and per-issue cards are preserved in
[`docs/archive/private-alpha-interim-issue-roadmap-2026-07-21.md`](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md).
They are evidence only and must not drive dispatch or completion.

Issue-specific completion evidence remains in `docs/reports/`; canon and active
release-discipline documents are never archived merely because a slice lands.

### Legacy issue-link compatibility

Existing GitHub issue bodies link to the former roadmap's issue anchors. Keep
those links resolvable while directing readers to the archived cards:

- <a id="issue-228"></a>[#228 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-228)
- <a id="issue-229"></a>[#229 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-229)
- <a id="issue-230"></a>[#230 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-230)
- <a id="issue-231"></a>[#231 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-231)
- <a id="issue-232"></a>[#232 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-232)
- <a id="issue-233"></a>[#233 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-233)
- <a id="issue-234"></a>[#234 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-234)
- <a id="issue-235"></a>[#235 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-235)
- <a id="issue-236"></a>[#236 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-236)
- <a id="issue-237"></a>[#237 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-237)
- <a id="issue-238"></a>[#238 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-238)
- <a id="issue-239"></a>[#239 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-239)
- <a id="issue-240"></a>[#240 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-240)
- <a id="issue-241"></a>[#241 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-241)
- <a id="issue-242"></a>[#242 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-242)
- <a id="issue-243"></a>[#243 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-243)
- <a id="issue-244"></a>[#244 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-244)
- <a id="issue-245"></a>[#245 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-245)
- <a id="issue-246"></a>[#246 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-246)
- <a id="issue-247"></a>[#247 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-247)
- <a id="issue-248"></a>[#248 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-248)
- <a id="issue-249"></a>[#249 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-249)
- <a id="issue-250"></a>[#250 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-250)
- <a id="issue-251"></a>[#251 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-251)
- <a id="issue-252"></a>[#252 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-252)
- <a id="issue-253"></a>[#253 archived card](../archive/private-alpha-interim-issue-roadmap-2026-07-21.md#issue-253)

## Program Boundary

The interim ends when the founder and the small private-alpha circle approve
all six live outcomes. It does not require closing every historical issue.

Out of scope for this pivot:

- A1b, A2, and A4 implementation;
- generic memory/RAG, embeddings, pgvector, or public excerpts;
- broker/export execution, voice-provider integration, native mobile, or a new
  engine platform;
- broad refactors not required by a selected user journey;
- production deployment or tester invitation without a separate founder
  decision.

## Global Stop Conditions

Stop and rescope when a lane:

- does not materially advance a remaining founder outcome;
- needs a canon/API/data-model decision the slice does not own;
- introduces an unapproved schema, public field, provider, or dependency;
- creates two owners for a protected runtime surface;
- restores phrasebook routing, a second chat brain, frontend-invented facts,
  generic RAG, or provider disclosure;
- spends real tokens or provider calls outside documented live gates;
- cannot roll back independently without discarding durable evidence;
- broadens into architectural refactoring;
- treats the audit donor as a merge source or acceptance evidence;
- reaches deterministic green without required live QA; or
- claims completion from a partial PR, scaffold, or checklist.

## Program Exit Criteria

- Representative conversations progress without loops or repeated recovery.
- Security, session, and Usage controls remain reachable and truthful.
- Result graphs continue switching ranges without changing canonical truth.
- Supported and unsupported requests receive honest, useful behavior.
- Search and suggestions are grounded.
- Omnisearch provides useful owner-scoped retrieval and navigation.
- Every promoted slice records exact SHAs, deterministic and live evidence,
  rollback, and remaining exposure gates.
- Tester exposure and production deployment remain separate founder decisions.
