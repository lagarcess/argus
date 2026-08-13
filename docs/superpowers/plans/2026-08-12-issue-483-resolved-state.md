# Issue #483 Resolved-State Clarification Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task.

**Goal:** Make the guest conversation advance from a resolved Coca-Cola DCA idea to confirmation after the user supplies the missing amount, without asking again for the asset in English or es-419.

**Architecture:** A successful asset preflight extraction owns the current turn's asset-mention result, including the valid empty result that means the user named no new asset. Failure fallback remains available only when extraction actually fails or returns an invalid schema. The existing typed strategy requirements remain the single owner of normal missing fields, while explicit incomplete provider context continues to block partial, ambiguous, unsupported, and overflowed baskets. Tests enforce that a clarification cannot request a field the canonical resolved strategy already satisfies.

**Tech Stack:** Python 3.10, Pydantic, LangGraph runtime, pytest, OpenRouter structured interpretation, Alpaca asset resolution.

## Scope Decision: Keep #455 Separate

Issue #483 and issue #455 share the split-brain pattern, but they do not share one runtime fact owner. Issue #483 is an interpreter preflight and clarification-state defect: a valid empty current-turn extraction is confused with provider failure, allowing a fallback extractor to invent a second asset state. Issue #455 is a domain and presentation defect spanning DCA contribution semantics, card projections, calendar behavior, and fractional-share assumptions. Combining them would expand this repair across different owners and acceptance surfaces without making either mismatch unrepresentable. This lane fixes #483 only and treats #455 as a separate coordinated fix.

## Constraints

- Original integration base: `bd96746f6f4c8d7948b6b6e5cec6d1113450847b`.
- Work only in `codex/issue-483-resolved-state` from the post-PR #479 integration head.
- Do not edit `.env`, `web/.env.local`, frontend copy, locale catalogs, database, API contract, deployment configuration, or DCA card semantics.
- Do not add regexes, localized phrase tables, language gates, or routing before LLM interpretation.
- Preserve the explicit-incomplete protection introduced for issue #336.
- Stop at a clean reviewed PR targeting `codex/private-alpha-next`. Do not merge or deploy.

---

### Task 1: Capture the fallback split-brain as a failing invariant

**Files:**

- Add: `tests/agent_runtime/test_issue_483_resolved_state.py`
- Add: `docs/reports/evidence/483/baseline.md`

- [x] Add an async preflight test whose primary model returns a valid empty `LLMAssetMentionExtraction` with completeness `true` and whose fallback would invent an incomplete asset. Assert the primary result is represented as explicit empty provider context and the fallback is never called.
- [x] Add a typed clarification invariant covering asset, capital, period, and cadence: once the canonical strategy satisfies a field, the response intent cannot request that field. Keep an explicit-incomplete asset case outside the resolved set so partial baskets remain blocked.
- [x] Add the inverse case: a genuinely empty `asset_universe` requests the asset exactly once.
- [x] Record the untouched-base deterministic contradiction and bilingual Guest live baseline, including source SHA, typed state, route outcome, and diagnostic provider cost. Store no environment values.
- [x] Run the focused tests and record RED against the untouched implementation.

### Task 2: Make valid empty extraction a first-class result

**Files:**

- Modify: `src/argus/agent_runtime/interpreter/asset_resolution_context.py`
- Test: `tests/agent_runtime/test_issue_483_resolved_state.py`

- [x] Change `provider_asset_resolution_context_from_extraction` so every valid schema result returns typed JSON, including `asset_resolution_candidates=[]` with `all_traded_asset_mentions_accounted_for=true`.
- [x] Keep `None` reserved for disabled preflight, exhausted exceptions, or invalid schema results in `provider_asset_resolution_context_for_request`.
- [x] Preserve explicit `false` when an extracted traded asset is unsupported, overflows the five-asset limit, or was omitted by the extractor.
- [x] Run the focused provider ownership tests and prove the valid empty result stops the fallback while actual failure still advances to the fallback.

### Task 3: Prove the resolved-field invariant through stages

**Files:**

- Modify: `tests/agent_runtime/test_issue_483_resolved_state.py`
- Modify only if the test exposes another owner: the smallest shared runtime boundary under `src/argus/agent_runtime/`

- [x] Replay the second-turn typed path with prior KO, DCA, monthly cadence, five-year dates, and the newly supplied amount. Assert confirmation is produced and no clarification requests `asset_universe`.
- [x] Parameterize the invariant across the canonical missing-field owners for asset, capital, date range, and cadence. Assert requested fields are derived from canonical unresolved state, not stale interpreter lists.
- [x] Preserve the reverse path where the asset is truly missing and ensure only one typed asset request is emitted.
- [x] Run focused stage tests, then the owning agent-runtime modules.

### Task 4: Verify the exact candidate and capture accepted live proof

**Files:**

- Add: `docs/reports/evidence/483/verification.md`

- [x] Run formatting, focused tests, the hermetic agent-runtime suite, mocked interpreter evals, spine guardrails, and the modularity budget.
- [ ] Fetch current integration and audit semantic overlap from the original base. If integration advanced, merge it one way into the worker and rerun affected deterministic gates.
- [ ] On the final behavior head, replay the exact three-turn Guest transcript through the real interpreter in English and the equivalent es-419 transcript. Assert the amount question on turn one, a confirmation artifact on turn two, no requested asset, and no backtest execution.
- [ ] Record the accepted provider-reported cost, exact source SHA, Guest traffic class, and sanitized route receipts. Do not store secrets or environment files.

### Task 5: Publish and exhaust review

- [ ] Commit the scoped changes with conventional commits and push `codex/issue-483-resolved-state`.
- [ ] Open a PR against `codex/private-alpha-next` with `Closes #483`, relevant existing labels, the #455 scope decision, deterministic evidence, bilingual live evidence, exact head, and accepted live cost.
- [ ] Wait for exact-head CI, request one Codex review round, and use the review-exhaust flow for every actionable finding.
- [ ] If a finding changes the head, rerun affected proof and request a delta-scoped review only after CI is terminal.
- [ ] Stop only when the latest-head review is clean and unresolved review-thread count is zero. Write the terminal audit after that state. Do not merge or deploy.
