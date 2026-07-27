# Grounded Discovery Search v1 Implementation Plan

Status: **COMPLETED BY PR #276 — post-merge flag policy changed 2026-07-27:
Grounded Discovery now defaults on; explicit false remains the kill switch**

> **For agentic workers:** steps use checkbox (`- [ ]`) syntax for tracking.
> TDD-first: every behavioral task pins a red matrix before implementation.
> The release captain owns integration, sequencing, and every founder gate.

**Goal:** Ship founder outcome 5 ("Discovery is grounded and Argus can
suggest") as designed in
`docs/superpowers/specs/2026-07-25-grounded-discovery-search-v1-design.md`:
explicit peer/category asset discovery through one typed route, one bounded
provider-neutral Search call, resolver-validated candidates, chip selection
into the normal confirmation lifecycle, honest typed recovery, EN/ES parity,
and a default-on Search flag with an explicit emergency kill switch.

**Architecture:** One new typed interpreter owner (`asset_discovery`) dispatches
from `stages/interpret.py` into a new cohesive `agent_runtime/discovery/`
composer. A provider-neutral `domain/discovery_search/` boundary owns the
Search call. Validation reuses `resolve_asset()`. Persistence is an additive
assistant-message metadata sidecar (`argus_discovery/v1`); no new tables, no
new API routes, no second brain.

**Tech Stack:** Python 3.10, FastAPI, LangGraph, Pydantic, httpx, React 19,
Next.js 16, TypeScript, pytest, Bun test, SSE.

## Global Constraints

- Base: integration checkpoint `50dff34c` on branch
  `claude/grounded-discovery-release-9cc859`; design commit `4d2db3de` is the
  behavior authority. Compare against `codex/private-alpha-next`, never `main`.
- Canon order applies (`AGENTS.md` → PRODUCT → API_CONTRACT → DATA_MODEL →
  ARCHITECTURE → DESIGN). The P2.0 spine invariants are release blockers: no
  text re-scan, no post-LLM intent override, no substring/alias matching over
  prose, no literal-text grounding, no per-language copy tables.
- **Spine ownership / serialization:** this lane is the single active owner of
  `agent_runtime/stages/interpret*.py`, `agent_runtime/llm_interpreter*.py`,
  and `agent_runtime/interpreter/*` while it runs. Other active lanes (guest
  experience, onboarding removal, focused UI cleanup) must not edit those
  files concurrently; if any lane lands interpreter or
  `web/components/chat/ChatInterface.tsx` changes into integration first, this
  lane rebases and re-verifies before publication. Shared-file overlap risk
  outside the spine: `ChatInterface.tsx`, `web/public/locales/*/common.json`,
  `.env.example` — rebase duty is on this lane.
- Zero live provider or LLM spend outside: (a) the founder-approved provider
  comparison (Task 6), (b) sanctioned live eval moments, (c) live browser QA
  (Tasks 7–8). All deterministic suites run hermetically
  (`ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture`, provider keys
  blanked) except tests that explicitly fake providers.
- Every task ends with: focused tests green, a conventional commit, and a
  one-commit-family revert path. No 50-file uncommitted diffs.
- **Credential sourcing:** this worktree keeps no `.env` (hermeticity is
  load-bearing). Live gates read `PERPLEXITY_API_KEY`/`OPENROUTER_API_KEY`
  from the main checkout's gitignored `.env` — injected per-process at
  invocation (Task 6) or staged as a temporary QA `.env` that is deleted when
  QA ends (Tasks 7–8). Keys are never committed, echoed, logged, or written
  into scorecards.
- **Globally forbidden surfaces:** `src/argus/api/routers/search.py`
  (Omnisearch), onboarding/guest code paths, `web/lib/private-alpha-flags.ts`
  additions (no new frontend flag), Supabase migrations, quarantine tags as
  merge sources, `main`/`codex/private-alpha-next` direct pushes, PostHog
  event registry, capability-registry semantics (#241 owns them).

## File Structure

```text
src/argus/domain/discovery_search/     # Task 1–2: provider-neutral boundary
  __init__.py  contracts.py  config.py
  perplexity_direct.py  openrouter_web_search.py
src/argus/agent_runtime/discovery/     # Task 3–4: conversational composer
  __init__.py  contracts.py  composer.py  extraction.py  validation.py
tests/agent_runtime/discovery/         # mirrors the modules
tests/domain/test_discovery_search_*.py
web/components/chat/…                  # Task 5: sidecar rendering
```

---

### Task 0: Baseline And Work Ledger

**Files:** none modified (read-only verification).

- [ ] **Step 1:** Confirm HEAD descends from `50dff34c` + design commit; tree
  clean; no untracked `.env`.
- [ ] **Step 2:** Record the hermetic baseline:

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/agent_runtime tests/test_spine_guardrails.py -q --no-cov
```

  plus `cd web && bun test` and the mocked eval harness. Store pass counts in
  the PR-draft notes; these are the regression baseline.

**Stop:** any pre-existing failure → report to founder before proceeding.
**Rollback:** n/a.

---

### Task 1: Provider-Neutral Search Boundary Contracts

**Files:**
- Create: `src/argus/domain/discovery_search/__init__.py`, `contracts.py`,
  `config.py`
- Create: `tests/domain/test_discovery_search_contracts.py`
- Modify: `.env.example` (flag/config block, documented defaults)
- Forbidden: everything under `agent_runtime/`, `api/`, `web/`.

**Interfaces produced:** `SearchResult`, `SearchResultPacket`,
`SearchUnavailableError`, `SearchProvider` protocol
(`search(query, *, max_results, timeout_seconds) -> SearchResultPacket`),
`discovery_search_config()` reading `ARGUS_GROUNDED_DISCOVERY_ENABLED`
(default false), `ARGUS_DISCOVERY_SEARCH_PROVIDER`,
`ARGUS_DISCOVERY_SEARCH_TIMEOUT_SECONDS=8`,
`ARGUS_DISCOVERY_MAX_CANDIDATES=5`, `ARGUS_DISCOVERY_HOURLY_LIMIT=10`,
`ARGUS_DISCOVERY_DAILY_LIMIT=25`.

- [ ] **Step 1: Red matrix**

```text
result_strings_are_bounded_and_sanitized   (title<=200, snippet<=1000,
  control chars stripped, non-https url rejected, url<=512)
packet_caps_results_at_five
source_date_optional_and_iso_validated
flag_default_off_and_config_parses_bounds  (timeout>0, candidates 1..5)
provider_protocol_raises_typed_unavailable
```

- [ ] **Step 2:** Verify reds → implement → green:

```bash
poetry run pytest tests/domain/test_discovery_search_contracts.py -q --no-cov
```

- [ ] **Step 3:** Commit `feat(discovery): add provider-neutral search boundary contracts`.

**Stop:** any need to import agent_runtime or api modules here.
**Rollback:** revert the single commit; pure addition.

---

### Task 2: Thin Provider Adapters

**Files:**
- Create: `src/argus/domain/discovery_search/perplexity_direct.py`,
  `openrouter_web_search.py`
- Create: `tests/domain/test_discovery_search_adapters.py`
- Forbidden: runtime wiring; any real HTTP in tests (mock the transport).

**Interfaces produced:** two `SearchProvider` implementations returning typed
packets with `latency_ms`, `retrieved_at`, `cost_usd` (provider-reported or
documented estimate), single attempt, typed `SearchUnavailableError` on
timeout/HTTP/parse failure. Adapter selection by
`ARGUS_DISCOVERY_SEARCH_PROVIDER`.

- [ ] **Step 1: Red matrix**

```text
perplexity_parses_documented_response_shape_with_source_dates
openrouter_parses_annotation_citations_without_date_guarantee
timeout_raises_typed_unavailable_within_configured_seconds
http_error_and_malformed_json_raise_typed_unavailable
no_retry_single_attempt_per_call
results_flow_through_task1_sanitization_bounds
unknown_provider_id_fails_closed_at_selection
```

- [ ] **Step 2:** Verify reds → implement (httpx with injected transport) →
  green:

```bash
poetry run pytest tests/domain/test_discovery_search_adapters.py -q --no-cov
```

- [ ] **Step 3:** Refresh official Perplexity Search + OpenRouter web-search
  docs (read-only fetch) and record any shape deltas versus the design in the
  adapter module docstrings and PR notes. Adjust parsers if the current docs
  disagree with the eval-scaffold-era assumptions.
- [ ] **Step 4:** Commit `feat(discovery): add perplexity and openrouter search adapters`.

**Stop:** docs reveal a shape that breaks the typed packet design → report to
founder before adapting the contract.
**Rollback:** revert commit; pure addition.

---

### Task 3: Typed Interpreter Owner And Honest-Recovery Route (SPINE)

**Files:**
- Modify: `src/argus/agent_runtime/llm_interpreter_types.py`
  (`asset_discovery` literal + `AssetDiscoveryRequest` + field)
- Modify: `src/argus/agent_runtime/llm_interpreter.py` (prompt guidance for
  the discovery boundary; EN/ES-agnostic instruction text)
- Modify: `src/argus/agent_runtime/stages/interpret.py` +
  `stages/interpret_types.py` (dispatch + decision plumbing only)
- Create: `src/argus/agent_runtime/discovery/__init__.py`, `contracts.py`,
  `composer.py` (recovery-only at this task)
- Create: `tests/agent_runtime/discovery/test_discovery_route.py`
- Modify: mocked eval fixtures (add EN/ES discovery classification +
  zero-search control cases)
- Forbidden: Search boundary calls (flag stays functionally off), frontend,
  API contract docs (shape not yet emitted).

**Interfaces produced:** `semantic_turn_act="asset_discovery"`,
`AssetDiscoveryRequest(relationship, category_description, anchor_symbols,
asset_class_hint)`, discovery dispatch that routes to
`discovery.composer.compose_discovery_response(...)`; at this task the
composer emits only typed honest recovery `discovery_unavailable` (flag off or
search not configured), voiced through the existing typed-recovery pattern.

- [ ] **Step 1: Red matrix (injected interpretations — no live LLM)**

```text
asset_discovery_act_routes_to_discovery_composer
discovery_outcome_not_overwritten_by_generic_result_followup
try_next_and_capability_questions_do_not_enter_discovery
direct_backtest_turn_never_constructs_search_provider  (fake provider spy = 0)
discovery_turn_preserves_pending_strategy_and_confirmation_state
flag_off_discovery_ask_yields_typed_discovery_unavailable_recovery
recovery_preserves_latest_result_reference
spanish_injected_interpretation_flows_identically
spine_guardrail_tripwires_stay_green  (no text re-scan introduced)
```

- [ ] **Step 2:** Verify reds → implement → green:

```bash
poetry run pytest tests/agent_runtime/discovery/ \
  tests/agent_runtime/test_interpret_stage.py \
  tests/test_spine_guardrails.py -q --no-cov
```

- [ ] **Step 3:** Run the full hermetic agent-runtime sweep (baseline
  comparison; zero regressions).
- [ ] **Step 4:** Commit
  `feat(discovery): add typed asset_discovery owner with honest recovery`.

**Stop:** any implementation pressure to re-scan `current_user_message`, flip
intent post-LLM, or add language-specific branches → stop and redesign the
typed data.
**Rollback:** revert commit family; interpreter returns to prior literals
(additive enum + optional field keeps old checkpoints compatible).

---

### Task 4: Flag-On Discovery Composer, Validation, Sidecar, Receipts, Quota

**Files:**
- Create: `src/argus/agent_runtime/discovery/extraction.py`, `validation.py`
- Modify: `src/argus/agent_runtime/discovery/composer.py` (full pipeline)
- Modify: `src/argus/llm/openrouter.py` (`discovery_extraction`,
  `discovery_voicing` task profiles with bounded budgets)
- Modify: `src/argus/domain/usage_limits.py` +
  `src/argus/api/chat/allowance.py` (`discovery_searches` resource,
  10/hour + 25/day, charged only on attempted Search)
- Modify: `src/argus/api/routers/agent.py` + `src/argus/api/chat/persistence.py`
  (attach `metadata.discovery` sidecar to the final payload and the persisted
  assistant message)
- Modify: route-receipt + cost-ledger hooks
  (`src/argus/api/chat/route_receipts.py`,
  `src/argus/observability/cost_ledger.py` call sites; `source="research"`,
  `feature_area="discovery"`)
- Modify: `docs/API_CONTRACT.md` + `docs/DATA_MODEL.md` in the same commit as
  the emitted shape (contract-first discipline)
- Create: `tests/agent_runtime/discovery/test_discovery_composer.py`,
  `test_discovery_validation.py`, `test_discovery_injection.py`
- Forbidden: frontend; provider adapters' internals; Omnisearch;
  capability-registry semantics.

**Interfaces produced:** full flag-on pipeline: quota check → one
`SearchProvider.search()` call → extraction LLM call (structured output, ≤8
raw candidates) → deterministic validation (`resolve_asset`, class check,
dedupe, cap 5) → voicing LLM call from validated facts → `argus_discovery/v1`
sidecar (≤5 sources, ≤5 candidates, ≤3 unverified names, provider id
excluded) → typed recoveries `discovery_search_failed`,
`discovery_no_verified_candidates`, quota-exhausted shape.

- [ ] **Step 1: Red matrix (fake provider + mocked LLM calls)**

```text
happy_path_emits_sidecar_with_validated_candidates_only
extraction_output_over_eight_or_malformed_is_bounded_or_recovered
unresolved_symbol_dropped_from_actions_but_may_appear_in_unverified_names
injected_instructions_in_snippets_never_alter_output_schema_or_policy
  (adversarial fixture: fake ticker dropped at resolution; no tool access)
sidecar_strings_bounded_and_provider_id_absent
search_called_at_most_once_per_turn
provider_unavailable_yields_search_failed_recovery_with_context_preserved
zero_validated_candidates_yields_no_verified_candidates_recovery
quota_charged_only_when_search_attempted_and_blocks_at_limit
receipt_and_cost_ledger_rows_record_latency_counts_and_research_source
voicing_receives_only_validated_typed_facts
turn_stays_within_existing_turn_deadline_machinery
```

- [ ] **Step 2:** Verify reds → implement → green:

```bash
poetry run pytest tests/agent_runtime/discovery/ -q --no-cov
```

- [ ] **Step 3:** Full hermetic sweep + mocked eval harness; zero regressions;
  `git diff --check`.
- [ ] **Step 4:** Commit
  `feat(discovery): grounded search pipeline with validation and sidecar`
  (docs included).

**Stop:** sidecar needs a new table or API route; validation needs
substring-matching over prose; any second Search call "just in case".
**Rollback:** revert commit family; Task 3 recovery-only behavior remains.

---

### Task 5: Frontend Sidecar Rendering, Chips, i18n, Reload

**Files:**
- Modify: `web/components/chat/ChatInterface.tsx` (render
  `metadata.discovery`: candidate chips via existing `chat_action` machinery,
  plain-text source/domain + locale-formatted dates, unverified-name prose is
  backend-owned)
- Modify: `web/components/chat/types.ts` (typed sidecar shape)
- Modify: `web/public/locales/en/common.json` +
  `web/public/locales/es-419/common.json` (chip labelKeys, freshness labels,
  recovery fallback strings)
- Create: `web/__tests__/discovery-sidecar.test.ts`
- Forbidden: new flags, new panels/cards beyond the message row, Omnisearch UI,
  onboarding surfaces, any state invention (render only what the sidecar
  provides).

- [ ] **Step 1: Red matrix (bun)**

```text
sidecar_renders_one_chip_per_candidate_with_label_and_labelKey
chip_tap_sends_normal_user_turn_text_with_chat_action_metadata
source_line_renders_domain_plus_locale_date_no_hyperlinks
reload_hydration_restores_chips_and_source_line_from_metadata
missing_or_legacy_messages_without_sidecar_render_unchanged
es_419_locale_renders_localized_freshness_and_labels
no_render_of_provider_or_internal_fields
```

- [ ] **Step 2:** Verify reds → implement → green: `cd web && bun test`.
- [ ] **Step 3:** i18n key-parity check for the new keys (en ↔ es-419).
- [ ] **Step 4:** Commit `feat(web): render grounded discovery candidates and sources`.

**Stop:** any need to infer state from prose or invent candidate data
frontend-side.
**Rollback:** revert commit; backend sidecar remains inert without renderer.

---

### Task 6: FOUNDER GATE — Live Provider Comparison And Selection

**Files:**
- Create: scratch probe script under `temp/` (not committed to runtime; the
  scorecard JSON lands in `temp/` and the summary in the PR description)
- Modify (after selection): `src/argus/domain/discovery_search/config.py`
  default provider + `.env.example` note
- Forbidden: runtime behavior changes; committing raw provider payloads.

- [ ] **Step 1:** Re-fetch current official Perplexity Search and OpenRouter
  web-search docs; present the exact probe list (~10 queries × 2 providers +
  1 forced-failure each, EN+ES, incl. one injection page), the rubric
  thresholds from design §4, and the **$5.00 hard ceiling** to the founder.
- [ ] **Step 2:** **WAIT for explicit founder approval of live calls + ceiling.
  No call before it.**
- [ ] **Step 3:** Run probes through the Task 2 adapters; record per-probe
  relevance, citation/url integrity, source dates, latency, cost, outage and
  injection behavior into a scorecard.
- [ ] **Step 4:** Present the scorecard; founder selects the provider. Set the
  default; commit `chore(discovery): select search provider from live scorecard`.

**Stop:** ceiling reached mid-run (halt immediately, report spend); both
providers miss the rubric (recommend defer/rework, founder decides).
**Rollback:** config revert; adapters remain for the follow-up arc.

---

### Task 7: Early Cohesive Live Browser QA (flag on, selected provider)

**Files:** fixes discovered here land as focused commits in their owning
task's files; no new surfaces.

- [ ] **Step 1:** Local QA-mode stack (real auth, `live_provider`,
  `ARGUS_GROUNDED_DISCOVERY_ENABLED=true`, selected provider key, Postgres
  checkpointer). Non-admin QA identity.
- [ ] **Step 2:** Drive J1 (standalone EN category), J2 (post-result peer with
  assumption preservation on selection), J4 (flag-off + forced outage), J5
  (direct backtest zero Search — verify via receipts/logs), one Spanish J1.
  Record receipts evidence (latency, counts, cost rows).
- [ ] **Step 3:** Fix reproduced issues TDD-first in their owning modules;
  rerun affected journeys.
- [ ] **Step 4:** Add the discovery classification acceptance cases to the
  live eval suite and run the sanctioned live moment once green
  (interpreter-facing live gate).

**Stop:** a journey failure that requires design change (not a bug) → back to
founder before code.
**Rollback:** per-fix commit reverts.

---

### Task 8: Internal Review, Simplification, Full Verification

- [ ] **Step 1:** Proportional internal review of the bounded diff versus
  `codex/private-alpha-next` (correctness, spine invariants, security/injection,
  contract/doc consistency, modularity, test quality). Fix confirmed, reachable
  findings only; smallest safe fix; discard disproportionate scope.
- [ ] **Step 2:** Simplification pass on the new modules (dead branches,
  needless machinery).
- [ ] **Step 3:** Full gates on the final candidate SHA: hermetic agent-runtime
  sweep + spine guardrails, discovery suites, mocked eval harness, `bun test`,
  focused ruff, `git diff --check`, i18n parity.
- [ ] **Step 4:** Exact-head full browser acceptance — the 12-point dispatch
  matrix, EN + ES, including reload truth, bounded calls/cost, injection
  posture, and at most one real backtest proving the selected candidate
  reaches the working path.

**Stop:** any red on the exact head; live QA disagreeing with green tests
(founder rule: live evidence wins).
**Rollback:** fixes are per-commit revertible.

---

### Task 9: Publication And Founder Handoff

- [ ] **Step 1:** Push `claude/grounded-discovery-release-9cc859`; open a
  **Draft PR** to `codex/private-alpha-next` containing: product behavior,
  evidence contract, provider scorecard summary + costs, browser-journey
  evidence, risks, rollback (flag kill switch + commit family), and remaining
  founder gates (merge, deploy/env/canary, tester exposure, #244 closure).
- [ ] **Step 2:** Let CI reach terminal state; fix reds with focused commits.
- [ ] **Step 3:** Post the #244 reconciliation comment (typed route delivered,
  provider selected with evidence, stale "#241 route" gate wording corrected,
  remaining exposure gates listed). No issue closure.
- [ ] **Step 4:** STOP. Founder owns external review, merge, and every later
  gate.

---

## Completion Mapping

| Dispatch browser-acceptance point | Proven by |
| --- | --- |
| 1 standalone category discovery | Task 7 J1 + Task 8 matrix |
| 2 post-result peer discovery | Task 7 J2 + Task 8 |
| 3 assumption preservation | Task 7 J2 selection + continuity tests (T3/T4) |
| 4 normal interpreter/confirmation lifecycle | Task 7 J2 + one real backtest (T8) |
| 5 zero Search on direct backtests | T3/T4 spy tests + T7 J5 receipts |
| 6 outage honesty + preserved state | T4 recovery tests + T7 J4 |
| 7 invalid candidates not actionable | T4 validation tests + T8 matrix |
| 8 EN and ES | T3 eval cases + T5 i18n + T7/T8 both languages |
| 9 reload preserves truth | T5 hydration tests + T8 matrix |
| 10 no auto-run / no recommendation claims | T4 composer tests + T8 review |
| 11 bounded calls/cost/latency/count | T4 receipts/quota tests + T6 scorecard + T7 evidence |
| 12 sources cannot modify policy | T4 injection fixture + T6 live injection probe |

Issue #244 acceptance criteria map to Tasks 3 (typed route, zero-search
controls, honest disabled behavior), 4 (bounded cited shortlist, validation,
untrusted sources, bounded/recorded spend, outage), 6 (approved provider), and
7–8 (EN/ES journey proof).
