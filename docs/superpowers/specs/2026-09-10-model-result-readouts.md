# Model text inside the existing result frames

Founder-directed 2026-09-10. Integration base:
`d0884c3de81f8c53d454ac4f68f461d3b5dd77e3`.

## 1. Why

The product promises explanations of computed results. The current Quick take
and Breakdown repeat typed facts while paid model drafts remain private.
PRODUCT.md sections 11 and 19 and the decision memo's EvidenceArtifact
clarification make these surfaces the interpretation attached to evidence.

## 2. Locked decisions

1. Preserve both frames, labels, order, and the result card.
2. Add one closed `result_readout_content` envelope with
   `schema_version: "result_readout/v1"`, `surface: "quick_take" | "breakdown"`,
   `language: "en" | "es-419"`, and `text: string | null`.
3. Write the envelope at composition time. Accepted model text is complete;
   failure stores null text and existing readout source/fallback/failure fields.
   Never expose partial text. Language aliases normalize at the shared boundary.
4. The reader shows accepted text only when the envelope version, surface, and
   current workspace language match. Missing, malformed, legacy, null-text, or
   mismatched envelopes use today's typed template. Reads never call a model or
   rewrite history. Legacy private prose fields remain forbidden.
5. Readouts saved before this lane have no envelope and remain template-only.
   A newly requested Breakdown on any run is a new message composed now and
   stamped with the current language. It never replaces the older readout.
   The creation stamp exists even when the new composition falls back.
6. Supply every stored run metric to both composers, including nested aggregate
   and per-symbol values, cost and activity fields. Stored chart data is optional;
   saved trade markers are not a complete ledger. Do not invent a path.
7. One shared grounding owner validates quoted numbers with rounding tolerance,
   contradictory benchmark claims, and exposed internal field/schema names.
   Remove required-mention rules and content caps. Document each kept/removed
   check and its rationale in the lane evidence report.
8. Prompt for a short first-glance Quick take and a deeper distinct Breakdown.
   Explain comparison, roughness and drawdown in human terms. A drawdown scaled
   to starting capital is explicitly an illustration, never an asserted actual
   peak-dollar loss. No unsupported causes, forecasts, advice, or em dashes.
9. Keep result_summary on chat and result_breakdown on context. No tier change
   without measured necessity; any authorized change belongs in openrouter_tasks.

## 3. Reserved scope

Keep changes confined to result readout generation, transport, presentation,
validation, documentation and proof. No environment-file writes, stash,
secret disclosure, render.yaml, release-contract edits, branch-protection
edits, PR merge or deploy.

## 4. Contract gates

- API_CONTRACT.md documents the closed envelope, transports and fallback rules.
- DATA_MODEL.md documents additive composition metadata, without a migration.
- Private-prose guards allow only the new closed readout transport.
- AGENTS.md surface ownership already matches; change only if semantics change.
- The approved $5 covers the targeted 48-task comparison and at most four
  fresh browser backtests. Finish this scope and targeted proof, then stop
  and report. Do not run the full live measurement or regenerate the prompt
  fingerprint without an explicit founder go. The founder alone merges PRs
  and deploys.

## 5. Execution contract and Goal

Deliver one non-draft PR targeting codex/private-alpha-next. The goal is a
complete language-safe generation, persistence and display path with focused
tests, bilingual durable browser evidence for fresh/legacy runs, a targeted
interleaved readout comparison, and exact DOCN/SPY preview instructions.

Implementation sequence:

- [x] Prove current generation, persistence, reader and validator boundaries.
- [x] Test and implement the shared generation facts and truth checks.
- [x] Test and implement creation-time transport and template fallbacks.
- [x] Test and implement matching-language frame content and clipboard parity.
- [x] Record every validator disposition and focused verification result.
- [x] Post a cost estimate and obtain founder approval: up to $5 total.
- [x] Commit targeted measured evidence and bilingual browser proof; leave the fingerprint unchanged.
- [ ] Check merged-tree modularity, exact-head CI and final clean Codex review
  with zero unresolved threads, then write the terminal audit.

The targeted stop checkpoint is recorded in
`docs/reports/evidence/model-result-readouts/README.md`. All 48 tasks were
attempted and reviewed; candidate quality passed 1/24. Browser proof includes
three UI backtests and a direct DCA fixture after its chat setup failed.
The writing bar, exact-head green CI and final clean review remain unmet.
This is a requested stop, not readiness. The founder merges and deploys.

## 6. Stop conditions

Stop and report any requirements contradiction or necessary forbidden edit.
Stay within the approved $5 and at most four fresh browser backtests. Stop
and report after the targeted proof. Full live measurement and fingerprint
regeneration require a separate explicit founder go.

## Sources

Authority: founder's lane brief; AGENTS.md; PRODUCT.md; ARCHITECTURE.md;
API_CONTRACT.md; DATA_MODEL.md; DESIGN.md; active grounded-finance roadmap;
private-alpha-next-decision-memo.md EvidenceArtifact clarification.

## 7. Founder-authorized second round

Continuation from `b66ff55a2a1673ae7a6323d248d42e5bd3706263`. The first
comparison failed; preserve its evidence. This is one further implementation
and measurement round, then a stop report. No merge, full live suite or
fingerprint regeneration is authorized.

1. Both composers consume one labeled fact sheet. Each stored numerical fact
   has a stable key, canonical value/unit, meaning, grain, basis and source.
   Distinguish executed fills from completed trades, annualized statistics
   from daily values, nominal chart extrema from ending equity, and starting
   capital from periodic and total contributions. Typed chart series may share
   meaning/unit metadata; their points remain individually referenceable.
2. Derive historical fixed-capital drawdown endpoints only when complete,
   ordered saved chart evidence and the pre-trade baseline support them and
   the derived percentage agrees with the stored metric. DCA nominal chart
   values cannot establish flow-adjusted drawdown dates; report unavailable
   when the underlying flow/risk path was not retained. Keep the capital-scaled
   money example explicitly an illustration.
3. Structured drafts report `language`, complete `text`, and `figures`. Each
   figure reports its `fact_key`, canonical `value`, exact visible `quote` and
   one-based occurrence. Code resolves each visible span, checks the key and
   value against that specific fact, checks the quoted rounding/unit and
   requires complete numeric coverage. Unknown, swapped, absent, overlapping
   or duplicate references fail the complete draft. Identity names such as
   S&P 500 are not numerical facts or a license to quote an unsupported 500.
4. The reported written language must match the requested workspace language.
   A mismatch or malformed report falls back atomically through existing
   provenance fields. No partial salvage, general language classifier,
   additional prose quotas or new causal/forecast rules are introduced.
5. References verify structured attribution; they cannot prove arbitrary
   natural-language entailment. The final comparison therefore reviews every
   accepted text for factual errors, including false relationships between
   individually true values. The bar is zero factual errors in accepted text.
6. Prepare 48 tasks for each tier setting using the same three genuine saved
   runs, both languages, four repetitions and both surfaces: 96 tasks total.
   Interleave current and structured settings. Both arms use the same corrected
   code; only the two readout task-tier mappings differ, exclusively in
   `src/argus/llm/openrouter_tasks.py`. Retain source hashes, raw drafts,
   structured references, failures, receipts, costs and quality dispositions.
7. Post an estimate after free exact-payload sizing, then wait for explicit
   founder approval before any paid execution. Earlier unused budget does not
   authorize this round. No fresh backtests or browser turns are included.
8. Push verified fixes and resolve review threads r3983053127 and r3983053137
   with their concrete evidence; this does not merge the PR. Report per-tier
   acceptance, fallback, quality pass and every factual error in accepted text.
   If neither tier has zero accepted factual errors, recommend keeping templates.

The existing frame, transport, history, privacy, no-touch and founder-merge
boundaries remain in force. The second-round evidence must not replace the
first round or become fingerprint authority.
