# Persisted artifacts follow the workspace language

One lane for #531, #530, and #528. English-authored results and confirmation
answers render from typed facts when viewed in a Spanish workspace.

Founder-approved 2026-09-04. Integration base: `5761dd417429895a24037df8231528c759af4179`.
The original base was `5d408acf`; the founder explicitly requested the rebase.

## 1. Why

`docs/PRODUCT.md` makes conversation continuity and reversible English/Spanish
workspace language part of Alpha. `docs/CONVERSATIONAL_RUNTIME.md` binds output
to the workspace language and makes immutable engine facts the result authority.
Hydration currently bypasses composition and paints saved English `content` and
`quick_take` under localized headings. Confirmation assumptions and previews
repeat the same defect through separate English string builders.

## 2. Locked decisions

1. Typed facts are the sole reader-facing source for the affected artifact
   surfaces. Frontend language bundles own their prose; Python contains no
   Spanish translations. Ordinary user text and unrelated conversational
   answers retain their existing transcript behavior.
2. Keep original LLM prose privately as immutable audit/model context. It must
   not feed result rendering, copy, previews, history, search dossiers, or a
   presentation fallback. Do not rewrite historical messages or run metrics.
3. Existing results benefit immediately: derive presentation from persisted
   `result_fact_bank`, typed card fields, and the owner-scoped canonical run.
   Repair missing old transport facts on read when the run identity exists.
   Missing evidence produces localized unavailable text, never English prose
   or invented metrics. No model call, per-language storage, or prose translation
   is triggered by reading or changing workspace language.
4. Result readouts and breakdowns share a typed result presentation contract.
   Preserve strategy shape, contribution roles/cadence, costs, date range,
   benchmark and availability. This lane changes presentation, not arithmetic.
5. Assumptions answers derive from the confirmation's `display_facts`, also
   used by its card. Remove the duplicate inferred/English assumption strips.
   Persist the typed answer and transport it through existing allowed seams so
   it renders both live and after reload without changing confirmation liveness.
6. Conversation previews are bounded read-time projections of the latest
   message's typed metadata. Their stored string remains private compatibility
   and search context; typed previews serve recents, archive, history and search.
   Preserve pagination, owner scope, ranking and message anchors.
7. Remove accepted-and-ignored language parameters from reachable helpers,
   delete dead helpers, and widen the existing AST tripwire to all five modules.
8. Add an AST architecture guard for retained prose: private prose readers have
   explicit ownership, presentation modules cannot access retained prose, and
   result rendering/copy must derive from the typed view model. Include negative
   mutation fixtures proving the guard catches a newly introduced template read
   and a compatibility fallback, not just today's implementation.
9. Preserve prompt builders and model schema descriptions where possible.
   Compare the observed fingerprint before and after. Any model-facing change,
   including one an extractor misses, requires the committed measurement
   scorecard under Never-Violate 12. Do not weaken fingerprint coverage.

## 3. Reserved / parked scope

- #533 is excluded, left open and untouched; do not change comparison arithmetic.
- No edits under `src/argus/llm/` or `src/argus/agent_runtime/interpreter/`.
- No edits to `web/components/chat/ChatInterface.tsx`,
  `web/components/chat/BacktestJobCard.tsx`, or `web/lib/chat-backtest-jobs.ts`.
- Receipt and sharing surfaces are excluded. No merge, deploy, hosted migration,
  research allowance changes, or backtest failure receipt changes.

## 4. Contract gates

- `docs/API_CONTRACT.md`: typed artifact answers/readouts/previews and hydration.
- `docs/DATA_MODEL.md`: immutable source prose versus reader presentation.
- `docs/CONVERSATIONAL_RUNTIME.md`: persisted artifact presentation boundary.
- Backend API schemas and matching TypeScript contracts, with OpenAPI updated
  through the repository's existing contract workflow if required.
- No database schema migration is planned: derive projections from existing
  message metadata and canonical run records.

## 5. Execution contract

- One worker PR into `codex/private-alpha-next`; founder merges.
- Commit this spec before implementation. Bounded parallel workers own result
  presentation, assumptions transport, and preview read paths; the release
  captain owns integration, privacy/AST guards, browser proof and final audit.
- Required proof: full `tests/agent_runtime/` and `tests/research/`; mocked eval
  harness; focused API, persistence, frontend and guard tests; type/lint/contract
  checks; modularity check against the reconciled integration tree.
- Baseline at integration: 2,258 passed, 2 failed (29.37s). Existing failures:
  `TestDiscoveryRouteFlagOff.test_detected_turn_language_reaches_discovery_composer`
  and `test_knowledge_turn_with_resolved_asset_is_not_interrogated`. Preserve
  their visibility. Prompt-freeze plus language suite: 128 passed.
- Capture durable browser before/after: author a result in English, switch to
  Spanish, reload it, verify localized Quick Take/body/copy and preview. Include
  a non-buy-and-hold strategy to cover cadence, money roles and costs. Commit
  screenshots and sanitized provenance under `docs/reports/evidence/531/`.
- The interpret-stage live gate applies; use the sanctioned pre-merge run and
  retain its scorecard. Reconcile newer integration one way without rebasing
  after committed evidence, assess semantic overlap, and report PR head and CI.

## 6. Stop conditions

- Report if the smallest correct fix requires one of the forbidden files or
  receipt/share surfaces, or cannot safely resolve an old artifact identity.
- Do not silently mutate persisted English prose or infer strategy facts from
  natural-language strings. Surface missing evidence honestly.
- Stop before founder-only merge/deploy or any unapproved paid evaluation beyond
  the sanctioned lane gate.

## Sources

### Argus authority

- Issues #531 (enumeration), #530 (assumptions fact owner), #528 (previews).
- Founder scope expansion and retention approval in this task.
- `AGENTS.md`, `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`,
  `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`, `.agent/designs/argus/DESIGN.md`.
- `docs/CONVERSATIONAL_RUNTIME.md`, `tests/evals/README.md`.

### Inference

- Read-time projection is sufficient because the witnessed English result
  already persists metrics and configuration in `result_fact_bank`. Older
  incomplete metadata can derive from the immutable owner-scoped run.
