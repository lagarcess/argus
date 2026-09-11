# Model text inside the existing result frames

Founder-directed 2026-09-10. Integration base:
`d0884c3de81f8c53d454ac4f68f461d3b5dd77e3`.

Historical decision log: later founder instructions superseded the earlier
provider restrictions and paid-check plans below. Current contracts live in
`docs/API_CONTRACT.md` and `docs/CONVERSATIONAL_RUNTIME.md`; completed merge
proof and measurement live in `docs/reports/evidence/model-result-readouts/README.md`.

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

## 8. Final founder-directed writing round

The founder declined the 96-task comparison and stopped the slot proposal.
Resume from `ab1fbda96678e7115fa798b8ec781022da180c3f` behavior. The
worktree was clean at that commit: no uncommitted slot implementation existed
to preserve on a local reference branch. No slot changes are authorized.

1. Change only the model writing brief in production. Keep the labeled fact
   sheet, response schema, figure-reference checks, benchmark contradiction
   check, internal-field check, language fallback, transport and templates.
2. The card owns numerical reporting. Quick take and Breakdown tell the
   historical story: the shape of the ride, what holding through it involved,
   and a supported next historical test when useful. They do not inventory or
   restate card figures. Use a figure only when needed to explain a point,
   through the existing exact fact references. Quick take stays first-glance;
   Breakdown adds depth without repeating it. Keep frames and actions intact.
3. Historical test suggestions are not investment advice, forecasts or claims
   about price causes. Story language must stay anchored to the supplied run;
   do not invent a path, recovery, holder emotion or missing trade history.
4. Prepare exactly twelve drafts from the same three genuine saved runs:
   English and Spanish, Quick take followed by Breakdown, one repetition,
   structured tier only. Change the two task-tier mappings only in
   `src/argus/llm/openrouter_tasks.py` in a clean isolated measurement checkout.
   Production lane mappings remain unchanged. Allow one provider HTTP attempt
   per frame task, with no provider retry or fallback call after that attempt.
   A failed or rejected attempt remains an outcome, not a reason to rerun it.
5. Measure complete request size without provider calls, retain the current
   output profiles and verified primary-model pricing, post a conservative
   estimate (expected near $3), and wait for explicit approval. Earlier budget
   approvals do not apply. No new backtests or market-data requests are included.
6. After approval, render every outcome in the browser beside the associated
   run's canonical source numbers. Accepted text uses the actual frames;
   rejected/unavailable outcomes show complete fallback, with any complete raw
   draft separately labeled as diagnostic and never misrepresented as accepted.
   Commit screenshots and source/provenance records. Browser rendering is
   provider-free and must not create additional model calls or backtests.
7. Report acceptance, fallback, writing quality, factual errors and cost for
   all twelve tasks, then stop. The fingerprint remains held. Do not merge,
   deploy, run the full live suite, write environment files, stash, or modify
   forbidden interpreter/research/release surfaces.

This final instruction supersedes the unpaid two-tier comparison plan, not its
preserved historical evidence. All runtime checks remain at `ab1fbda9` behavior.

## 9. Founder-locked Luna design and additive client boundary

This section supersedes section 8's unpaid structured-tier experiment and its
writing-only implementation boundary. No prior paid approval carries forward.
The existing frames, result card, saved-language behavior and complete template
fallback remain the reader contract.

1. Quick take uses `openai/gpt-5.6-luna` through OpenRouter, without search, on
   a new `readout` tier. `ARGUS_READOUT_MODEL` and
   `ARGUS_READOUT_FALLBACK_MODEL` both name that model. A Luna failure uses the
   template; no weaker model fallback. Chat retains its other tasks and keys.
2. Breakdown uses a readout-owned Luna model constant through the existing
   Perplexity Agent client, with `web_search` and `fetch_url` only. No
   `finance_search`. Its own Agent request deadline replaces the OpenRouter
   timeout wrapper. The context tier retains `capability_conflict` and its keys.
3. Add exactly one public structured-output method to `PerplexityAgentClient`.
   It accepts the caller's output schema and instructions and returns the
   complete validated draft, sources and usage. Reuse existing request, auth,
   timeout, usage, pricing and unpriced-spend handling. Add imports/supporting
   declarations if needed, but do not modify or delete any existing line in
   `src/argus/domain/research/perplexity_agent.py`. The existing research entry
   points and request builder are unchanged. `research/config.py` and
   `agent_runtime/research_grounded.py` remain byte-identical.
4. Keep the labeled run fact sheet and exact run references as the only source
   for backtest figures. Web context has separate source citations and dates;
   it never changes, replaces or joins the stored run facts. A web figure must
   reference its source and date; uncited figures reject the whole draft.
   Historical explanatory context must cite its source and distinguish
   reported events from an inferred contribution to a price move. No forecast
   or investment advice is introduced. Model-reported language still gates
   complete acceptance. Quick take remains search-free.
5. The card owns numerical reporting. Readouts tell the historical story,
   holding experience, tradeoffs and useful next historical test. A figure
   appears only when the sentence needs it, with its proper run or web reference.
   Quick take is first-glance; Breakdown develops rather than repeats it.
6. Remove the Breakdown OpenRouter task literal, profile, tier mapping, call,
   dependency injection and old timeout constant, including tests that pin
   that provider wiring. Preserve the `result_breakdown` message/presentation
   kind. OpenRouter Quick take receipts keep their existing accounting path.
   Every Perplexity Breakdown invoice reaches the shared research cost-ledger
   path, including rejected drafts; unpriced spend uses the existing recorder.
7. Propagate both readout keys through model environment owners, task registry,
   `.env.example`, local-QA and GitHub environment scripts, Render sync lists
   and requirements, release profile, `render.yaml`, runtime docs and tests.
   These release/environment edits are explicitly founder-authorized. Never
   write `.env` or `web/.env.local`; local values are process-only. Report the
   exact two lines the founder must add. Other tier keys retain their meaning.
8. Add Luna's research pricing row from the first approved response's billed
   input/output usage, retaining raw response evidence. Published prices may
   support the preflight estimate but are not billed-rate evidence. Unknown
   or mismatched pricing must remain visible through unpriced spend.
9. Prepare the same three genuine saved runs in English and Spanish, both
   frames, exactly twelve drafts, one attempt per frame. No new backtests.
   Bound input/output/tool work, post a fresh estimate, and wait for explicit
   approval before any paid call. Retain every outcome, raw response, receipt,
   accepted/fallback status and factual/quality review. Render all twelve
   outcomes in the browser beside their source numbers and commit screenshots.
10. Search `src`, `tests`, `docs`, `scripts` and `.github` for obsolete readout
    provider/tier wiring and report the disposition of every category found,
    distinguishing immutable historical evidence from active runtime contracts.
    Keep the fingerprint held; no full live eval, merge, deploy or stash.

Before approval, complete implementation, deterministic verification and the
bounded measurement setup. After approved proof, report its results and the
remaining held release gates. Stop if any required change exceeds the precise
additive client boundary or touches either other forbidden research file.

## 10. Reload persistence and computed headline facts

Founder-directed follow-up, 2026-09-11. This supersedes the canceled harness
and prior demo scope. Keep the current light figure checks, Sources panel,
language fallback, provider wiring and single working frame.

- Give Breakdown completion an owner independent of the browser stream.
  Reuse research job rows, task retention and message-first settlement in
  production. The existing development memory mode has no job endpoint; its
  existing ordinary-turn lifecycle must still persist completion after the
  requesting stream disconnects. Do not add another provider client.
- Supply the already computed drawdown dollar loss beside its dated endpoints,
  plus the whole-period peak date and a chronological headline event list.
  Compute from unrounded stored evidence, then apply card display rounding.
  Keep series and markers out of the Breakdown request; missing evidence stays
  unavailable. Do not change acceptance checks to police model arithmetic.
- Prove cancellation followed by successful persistence, reload hydration,
  one working state and source-panel continuity with focused free tests.
  Repeat only DOCN buy and hold and SPY RSI in English and Spanish in the real
  app, including a reload during generation. Record drafts, screenshots,
  sources and provider invoices; stop paid work if known billed spend exceeds
  the founder-authorized $2 round limit, and report uninvoiced attempts.
- Push the fixes and durable evidence to PR #588. Keep the prompt fingerprint
  held. No full live measurement, environment-file writes, stash, merge or
  deployment. Existing forbidden research files remain untouched. Stop and
  report if a required change cannot fit those boundaries.
