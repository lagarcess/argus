# Share the answer: reconciliation audit

Date: 2026-09-09. Read-only review of the fetched integration delta; no runtime,
database, provider, service, environment or Git mutation was performed by this
audit. This report is the only file written. Tests below are recommendations for
the reconciled head, not claims that this audit ran them.

## Reviewed revisions

- Original integration base: `743dfda3da9b467d32023ac32e900dad5a392500`.
- Current integration: `377190bd2911959e14ad9d92f2f4dba3edeb8453`, including PR #571.
- Sharing worker inspected: `746b7b745f7cd1ed35916587a508a95e8312ef80`.
- Integration delta: nine files, limited to research spend accounting and its
  producer/failure seams, the focused discarded-spend tests, API documentation
  and the board. Line references prefixed **I** refer to the integration
  revision above; **W** refers to the inspected worker revision. The captain subsequently merged this revision at `070aab20be941980391e5dde90117ab814553324`.

## Conclusion

The delta has semantic overlap with sharing at the typed research sidecar and
background-job settlement boundary. It does not invalidate the saved successful
English/Spanish research answers or their public rendering evidence. The new
billed failure and withheld paths cannot pass the worker's existing eligibility
projection. No sharing fix, new migration, paid research request, real backtest,
or broad browser matrix is justified by this delta.

Reconcile normally, run the focused deterministic checks and bounded saved-turn
replay below, and explicitly retain the existing browser evidence at the final
head. This conclusion is not a READY claim or a substitute for exact-head CI and
review.

## Semantic overlap by owner

| Surface | Disposition and evidence |
| --- | --- |
| Runtime owner | **Overlap.** `research_grounded.py` now accumulates every provider invoice through `_TurnSpend` (**I:120-158**), composes missing-publisher failures from the paid packet (**I:307-332**), and supplies actual spend to unavailable turns (**I:682-727**). Sharing reads the resulting typed metadata through `public_excerpt_selection._project` (**W:135-209**) and `public_excerpt_turns.project_research_turn` (**W:156-220**); it never reads the invoice to decide eligibility. |
| API/data contract | **Overlap in the private research sidecar's usage semantics, not in the public receipt contract.** `ResearchUnavailableError.usage`, `combined_research_usage` and `BackgroundPoll.usage/failure_reason` are added in `domain/research/contracts.py` (**I:154-172,217-251,304-315**). The research-sidecar version and source shape are unchanged. `public_excerpt_schemas.PublicExcerptResearchTurn` remains closed and has no usage/provider fields (**W:218-245**). The integration API prose must be retained alongside the worker's separate Public evidence receipts changes. |
| UI state owner | **No changed UI files.** A failed research job still fails canonical job settlement. `JOB_RESULT_HYDRATEABLE` requires `job_succeeded` in `domain/job_settlement.py` (**W:44-60**), and sharing invokes the existing predicate through `_memory_result_hydrateable` (**W public_excerpt_selection.py:157-179**). The ledger's `status = succeeded` is telemetry and cannot authorize sharing. |
| Migration | **No overlap.** PR #571 adds no migration or receipt persistence change. The worker's receipt-selection migration and existing source-deletion/revocation spine are untouched. |
| Environment variable | **No overlap.** The integration delta changes no environment declarations, feature defaults, credentials or deployment configuration. Sharing flags remain under the existing founder-controlled gate. |
| Directly affected tests | **Producer/consumer boundary.** The added `tests/research/test_discarded_spend.py` covers the producer; `tests/test_public_excerpt_turns.py` covers its receipt consumer. No frontend, receipt SQL, or version 1 formatter changed in the integration delta. |

## Failure paths stay ineligible

1. **Missing public publisher after paid attempts.** The integration path passes
   `withheld_code="research_unavailable_missing_public_sources"` explicitly
   (**I research_grounded.py:317-331**). That code wins over packet-derived
   classification, replaces the prose with the honest note and clears peers
   (**I:384-435**). The sidecar builder stores `degraded={code: ...}` and clears
   retrieved rows (**I:1685-1708**). The worker refuses a truthy `degraded` before
   copying fields, and independently refuses empty sources
   (**W public_excerpt_turns.py:164-176**). Published-looking prose or a nonzero
   invoice cannot override either check.

2. **Inline billed response rejected by the parser.** The provider parser reads
   usage before parsing and attaches it to the typed unavailable error
   (**I domain/research/perplexity_agent.py:204-229**). `unavailable_result`
   carries that spend but always supplies `research_unavailable_<reason>`
   (**I research_grounded.py:707-725**). The same degraded refusal applies.

3. **Thorough billed failure.** `poll_background` returns `status="failed"`
   with invoice evidence (**I perplexity_agent.py:118-126**). `_fail_job`
   sends a separately built degraded, source-empty object directly to
   `record_research_turn_evidence`, then marks the canonical job failed
   (**I api/chat/research_jobs.py:461-492**). The visible failure message still
   contains only `conversation_mode="guide"`, with no research sidecar
   (**I:503-520**). It fails the job-completion predicate; even an adversarial
   copy of the ledger-only sidecar would fail degraded/source eligibility.

4. **No spend/provider leakage through eligible success.** The public
   research projection names each allowed field explicitly and then audits the
   serialized document (**W public_excerpt_turns.py:197-210**). It never spreads
   message metadata or the research sidecar. `usage`, `capability_class`,
   `shape`, `rows`, `peers`, provider/model names and token fields have no public
   model slot (**W public_excerpt_schemas.py:232-245**). The ledger's provider,
   source ids, cost and latency stay in the existing telemetry writer
   (**I api/chat/research_evidence.py:262-308**).

## Evidence retained and limits

The saved successful `en-focused` and `es-419` cases record balanced research,
respectively two and five typed sources, no degraded code, and no provider retry
(`docs/reports/evidence/share-answer/research-provenance.json:16-38`). The initial
English timeout remains failure evidence and was never counted as successful
research proof (`:2-14`).

For a single provider response, `combined_research_usage` returns that same
usage object (**I contracts.py:226-229**). The success path retains the selected
packet's answer, sources and retrieval time; only its usage is replaced by the
turn-total copy before the existing composer (**I research_grounded.py:333-346**).
The successful packet already has sources, so the retrieval predicate is true
independently of invoice counts (**I:897-917**). The new peer guard skips work
only for an already withheld answer; its successful branch retains the prior
resolver logic (**I:389-419**). Successful background persistence and the
source-question relationship are unchanged.

The existing real-turn adversarial record already proves unchanged answers and
sources, private-metadata exclusion and degraded/missing-source refusal for both
saved languages (`docs/reports/evidence/share-answer/real-turn-adversarial.json`).
Retain research pages, selection/refusal UI, Settings/revoke/tombstone, preview
cards, guest-entry and version 1 body evidence. These artifacts establish saved
content and behavior; they do not establish the new accounting totals and should
not be relabeled as a new live provider measurement.

## Focused revalidation after reconciliation

- Run `tests/research/test_discarded_spend.py`. Its concrete checks include
  missing publishers (**I:97,136**), kept/discarded retries (**I:174,205**), billed
  unreadable/invalid envelopes (**I:231,256,279**), cached successful packets
  (**I:410,452**) and billed thorough failures (**I:585,640**).
- Run `tests/test_public_excerpt_turns.py`, especially
  `test_refusal_refuses_whole_selection_and_candidates_name_reason`
  (**W:142-168**), the exact closed projection (**W:99-127**), and
  `test_background_research_uses_canonical_job_settlement_and_original_question`
  across succeeded/running/failed (**W:335-361**).
- Reuse the saved real English/Spanish turns in memory. Confirm answer/source
  bytes and payload digest are unchanged when private usage carries summed,
  null or cache-hit accounting and provider/model extras. Confirm each new
  unavailable code remains unselectable, including a degraded sidecar with
  retained publisher sources. Confirm a billed thorough failure note fails
  with the canonical failed job and original request linkage. No durable writes
  or provider calls are needed.
- Run the normal required deterministic/OpenAPI/modularity/CI gates at the
  reconciled head. The overlap itself does not justify repeating paid evals,
  browser matrices, Auth/Postgres acceptance, or real backtests.

No active audit follow-up remains. The release captain owns reconciliation,
the bounded checks and final evidence/review bookkeeping.

## Captain verification after merge

The reconciled tree passes 528 focused backend cases, including all 20 discarded-spend cases and 88 receipt-turn cases. Saved real English/Spanish turns pass 18 existing adversarial refusals, six private-usage payload/digest invariance checks and eight new degraded/failed-job refusals. No provider calls or database writes occurred. All 20 signed-out public cases retain identical text, noindex, no cookies and no overflow. The merged-tree modularity check passes. Exact final-head CI and Codex disposition belong to the terminal PR audit.
