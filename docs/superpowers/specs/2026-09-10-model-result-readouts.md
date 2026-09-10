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
5. A run saved before this lane has no envelope and remains template-only,
   including a newly requested Breakdown. The creation stamp exists even when
   the new Quick take fell back. The founder has been asked to confirm this
   literal interpretation of the brief; any correction updates this contract.
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

Decision 10 owns unsupported_admission.py, llm_interpreter.py,
clarification_contract.py, chat-recovery-display.ts, research routing,
future-performance measurement cases, PRODUCT.md, and
chat.clarification.future_performance in both locale catalogs. This lane owns
chat.result_readout. No environment-file writes, stash, secret disclosure,
render.yaml, release-contract edits, branch-protection edits, merge or deploy.

## 4. Contract gates

- API_CONTRACT.md documents the closed envelope, transports and fallback rules.
- DATA_MODEL.md documents additive composition metadata, without a migration.
- Private-prose guards allow only the new closed readout transport.
- AGENTS.md surface ownership already matches; change only if semantics change.
- Prompt fingerprint changes require committed, founder-approved live evidence.

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
- [ ] Post a cost estimate and wait for founder approval before live work.
- [ ] Commit measured evidence and fingerprint; capture bilingual browser proof.
- [ ] Recheck PR overlap and current integration, reconcile one-way as needed.
- [ ] Check merged-tree modularity, exact-head CI and final clean Codex review
  with zero unresolved threads, then write the terminal audit.

The founder merges and deploys. Local tests and mocked browser checks are
development evidence, not a substitute for the approved live proof.

## 6. Stop conditions

Stop and report any requirements contradiction or necessary forbidden edit.
Do not run paid measurements or provider-backed browser turns before the founder
approves the concrete estimate. If integration changes fingerprinted text,
compare overlap, rerun this lane's affected measured cases, and regenerate its
fingerprint without changing decision 10's owned files.

## Sources

Authority: founder's lane brief; AGENTS.md; PRODUCT.md; ARCHITECTURE.md;
API_CONTRACT.md; DATA_MODEL.md; DESIGN.md; active grounded-finance roadmap;
private-alpha-next-decision-memo.md EvidenceArtifact clarification.

Initial live GitHub overlap check: no open PRs on 2026-09-10.
