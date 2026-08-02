# Issue #336 Opening-Turn Asset Continuity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve provider-resolved opening-turn assets and ask only for the genuinely missing period in the exact issue #336 reproduction.

**Architecture:** Fix the shared provider-context normalization boundary so a resolved traded asset clears the stale typed `asset_universe` blocker and invalidates stale clarification prose only when provider context explicitly proves that every extracted traded-asset mention was accounted for. Keep the LLM as the only natural-language interpreter; deterministic code reconciles only provider-owned typed facts. Add the exact prompt to the permanent typed eval manifest and prove it through the full live interpreter gate.

**Tech Stack:** Python 3.10.20, Pydantic v2, LangGraph runtime, pytest, YAML measurement eval fixtures, OpenRouter live eval.

## Global Constraints

- Start from fetched `origin/codex/private-alpha-next` at `6533377c1a08539136a622a7d53eee20d0efd845`.
- Do not add regexes, localized aliases, company-name tables, or a pre-LLM route.
- Do not change date interpretation; the expected result remains a `missing_period` clarification.
- Do not change frontend, API, database, provider selection, model routing, quotas, or OpenAPI.
- Use provider-backed asset identity; never hardcode `Apple -> AAPL` in production.
- Stop at a Draft PR targeting `codex/private-alpha-next`; the founder merges.

---

### Task 1: Reconcile Provider-Resolved Asset State

**Files:**
- Modify: `src/argus/agent_runtime/interpreter/asset_resolution_context.py`
- Modify: `src/argus/agent_runtime/interpreter/provider_context_assets.py`
- Test: `tests/agent_runtime/test_provider_asset_ownership.py`

**Interfaces:**
- Consumes: `response_with_provider_context_assets(response, *, asset_resolution_context, include_unsupported_request=False) -> LLMInterpretationResponse`, provider-owned `asset_resolution_candidates` rows, and the runtime-owned `all_traded_asset_mentions_accounted_for` completeness flag produced by asset extraction/resolution.
- Produces: the same response type with a canonical asset, stale `asset_universe` missing-field state removed, stale assistant clarification prose cleared, and remaining typed blockers preserved.

- [ ] **Step 1: Write the failing normalization regression test**

Add a test whose input response is a new `strategy_drafting` turn with `strategy_type="buy_and_hold"`, `capital_amount=10000`, no model-authored asset, `missing_required_fields=["asset_universe", "date_range"]`, `requires_clarification=True`, and stale asset-question prose. Supply one provider-owned resolved context row for `Apple`/`AAPL`. Assert the output has:

```python
assert draft.asset_universe == ["AAPL"]
assert draft.asset_class == "equity"
assert normalized.missing_required_fields == ["date_range"]
assert normalized.requires_clarification is True
assert normalized.assistant_response is None
assert "provider_context_resolved_missing_asset" in normalized.reason_codes
```

Production mutation caught: removing typed-blocker reconciliation while leaving asset injection intact must fail this test.

Add a negative case that sends provider extraction one resolved mention (`Apple`) and one unsupported traded-asset mention (`fictional moon fund`) while the model draft remains stale and empty. Assert the provider context records `all_traded_asset_mentions_accounted_for == False`, preserves `AAPL` as grounded partial context, keeps `asset_universe` in `missing_required_fields`, and never adds `provider_context_resolved_missing_asset`. Removing the completeness guard must fail this test by silently dropping the unsupported basket member.

Add a cap-boundary negative with five traded provider rows followed by a sixth distinct traded/unknown mention. Assert the first five unique resolved asset identities remain bounded but `all_traded_asset_mentions_accounted_for == False`. Add the inverse case where `Apple` and `AAPL` resolve to the same canonical symbol and asset class before four other distinct assets; assert the duplicate consumes one slot, all five unique assets survive, and completeness remains true. Add an alias-plus-overflow negative where six returned raw spans collapse to five provider identities but a required `all_traded_asset_mentions_included == False` signal proves another traded span was omitted. Add a cross-class symbol-collision negative proving matching canonical symbols in different asset classes remain separate in provider records and through response, capability, and stage canonicalization so the mixed-asset guardrail can see both. Assert the production extraction schema has `maxItems == 6`, requires the inclusion signal, and the prompt asks for it while prioritizing traded/unknown spans; do not expose downstream provider-context or reconciliation machinery in model guidance. Prove a benchmark row is separate from the five traded slots. Carry the resulting blocker through the full interpret stage, draft-only unsupported-strategy filtering, and active-artifact edit-planner response replacement on normal, model-failure, replay-recovery, and final planner-fallback paths, including planner-owned clarification responses; none may confirm or erase the truncated basket need. Add a planner negative that returns a full active-artifact draft containing inherited assets absent from the current-message provider rows and prove it remains confirmable. Add a negative for a planner reply represented as `conversation_followup` with semantic turn act `unsupported_request`; its limitation explanation must remain intact instead of being replaced by asset clarification. Add benchmark-only and zero-row unsupported negatives so empty traded candidates cannot bypass explicit incompleteness. Preserve tri-state compatibility: a missing measurement is unknown and must not be treated as explicit false.

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```bash
poetry run pytest tests/agent_runtime/test_provider_asset_ownership.py::test_runtime_context_asset_clears_stale_missing_asset_clarification -q --no-cov
```

Expected: FAIL because `missing_required_fields` still includes `asset_universe` and stale assistant prose remains.

- [ ] **Step 3: Implement the minimal typed reconciliation**

Inside `response_with_provider_context_assets`, after provider-owned resolved symbols have populated the draft:

```python
resolved_missing_asset = (
    response.intent in {"strategy_drafting", "backtest_execution"}
    and "asset_universe" in response.missing_required_fields
    and bool(resolved_symbols)
    and not ambiguous_fields
    and not preserved_fuller_draft
    and all_traded_asset_mentions_accounted_for
)
```

The extraction schema accepts up to six distinct mentions, requires `all_traded_asset_mentions_included`, and uses generic guidance to prioritize traded/unknown spans and report false if that limit omits one. Provider context retains at most five unique resolved traded asset identities while benchmark rows use their own slot. Resolve before applying the cap so two different spans with the same provider-owned canonical symbol and asset class consume one traded slot; matching symbols in different asset classes remain separate in provider records and through every canonicalization boundary for mixed-asset validation. Ambiguous rows still consume a slot because no canonical identity is available. The asset-resolution preflight sets `all_traded_asset_mentions_accounted_for` to false whenever the extraction inclusion signal is false, a traded/unknown extracted mention cannot produce a resolved or ambiguous provider row, or a sixth unique traded mention remains beyond the five-asset cap, and carries explicit false even when no rows survive. Explicitly incomplete context adds or retains `asset_universe` in `missing_required_fields`, forces clarification, and invalidates confirmation or unrelated prose even if the model already returned a nonempty five-symbol draft or only benchmark/no rows survived. A missing measurement is neutral. The `provider_context_incomplete_asset_mentions` reason code makes the blocker survive stage required-field recomputation and the draft-only unsupported-strategy missing-field filter. After active-artifact planning replaces a response, normal, model-failure, replay-recovery, and final planner-fallback returns reapply only the explicit-false integrity blocker, including when the planner returns its own clarification. They do not run full provider-row reconciliation again because the planned draft can include inherited artifact assets not mentioned in the current message, and they exclude responses whose semantic turn act is `unsupported_request` so planner limitation explanations survive intent-level `conversation_followup` representation. When the full condition is true, remove only `asset_universe` from `missing_required_fields`, clear `assistant_response`, retain clarification when another typed blocker such as `date_range` remains, and append `provider_context_resolved_missing_asset` once to `reason_codes`. Do not apply the blocker-clearing reconciliation to unsupported turns, ambiguous rows, overflowed extraction, or partial provider context.

- [ ] **Step 4: Run focused GREEN and the owning module**

Run:

```bash
poetry run pytest tests/agent_runtime/test_provider_asset_ownership.py -q --no-cov
poetry run pytest tests/agent_runtime/test_llm_interpreter_semantic_contracts.py -q --no-cov
```

Expected: both commands pass with zero failures.

- [ ] **Step 5: Commit the shared-boundary fix**

```bash
git add src/argus/agent_runtime/interpreter/asset_resolution_context.py src/argus/agent_runtime/interpreter/provider_context_assets.py tests/agent_runtime/test_provider_asset_ownership.py
git commit -m "fix(chat): preserve opening-turn resolved assets"
```

### Task 2: Add Exact Typed Eval and Complete Delivery Gates

**Files:**
- Modify: `tests/evals/measurement_cases/messy_english.yaml`
- Modify: `tests/evals/measurement_eval_harness.py`

**Interfaces:**
- Consumes: the measurement-eval fields `intent`, `capability_verdict`, `assets`, `asset_class`, `strategy_type`, `capital_amount`, `stage_outcomes`, and the added typed `requested_field` measurement.
- Produces: permanent case `messy_english_opening_apple_capital_missing_period_issue_336` used by mocked manifest validation and sanctioned live evaluation.

- [ ] **Step 1: Add the exact acceptance fixture**

Add this case to `messy_english.yaml`:

```yaml
  - id: messy_english_opening_apple_capital_missing_period_issue_336
    prompt: "let's test apple with 10K"
    user_language: en
    ui_language: en
    expected:
      intent: ["backtest_execution", "strategy_drafting"]
      capability_verdict: needs_clarification
      assets: ["AAPL"]
      asset_class: equity
      strategy_type: buy_and_hold
      capital_amount: 10000
      stage_outcomes: ["needs_clarification", "await_user_reply"]
      requested_field: date_range
```

Production mutation caught: dropping the opening asset or re-requesting `asset_universe` fails the typed asset and clarification assertions without relying on prose.

- [ ] **Step 2: Validate the fixture and mocked eval contracts**

Run:

```bash
poetry run pytest \
  tests/evals/test_measurement_eval_harness.py \
  tests/evals/test_chat_runtime_eval_manifest.py \
  tests/evals/test_chat_runtime_trajectory_harness.py \
  -q --no-cov
```

Expected: zero failures and no provider calls.

- [ ] **Step 3: Run the focused and hermetic runtime gates**

Run:

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/agent_runtime tests/test_spine_guardrails.py -q --no-cov
```

Expected: zero failures, seconds-scale execution, and no live provider receipts.

- [ ] **Step 4: Review the exact diff proportionally**

Verify every spec decision against the diff: provider-owned identity only, no text scan, date handling untouched, no unsupported/ambiguous escalation, and the exact typed case present. Run:

```bash
git diff --check origin/codex/private-alpha-next...HEAD
git diff --stat origin/codex/private-alpha-next...HEAD
git diff origin/codex/private-alpha-next...HEAD -- \
  src/argus/agent_runtime/interpreter/asset_resolution_context.py \
  src/argus/agent_runtime/interpreter/provider_context_assets.py \
  tests/agent_runtime/test_provider_asset_ownership.py \
  tests/evals/measurement_cases/messy_english.yaml \
  tests/evals/measurement_eval_harness.py
```

- [ ] **Step 5: Run the sanctioned full live eval once on the exact candidate**

Run:

```bash
ARGUS_RUN_LIVE_EVALS=1 ARGUS_EVAL_ENV_FILE=.env \
ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider \
poetry run pytest tests/evals/test_measurement_eval_live.py -q --no-cov
```

Expected: full suite passes with no unexpected failures; the scorecard records the issue #336 case as passed. If it fails, do not loop speculative provider calls—retain the scorecard and route-receipt evidence and stop per the spec.

Observed regression diagnosis after the first post-review exact-head gate: implementation-heavy extraction wording produced a valid empty list in the issue #336 case. Exact head `9c151fcd` was mixed at **2 pass / 3 fail**, while clean integration `6533377c` passed **5 / 5**. Replacing downstream overflow language with the generic six-item schema/prompt contract restored the candidate to **5 pass / 0 fail** before commit. Preserve those scorecards with the PR evidence.

- [ ] **Step 6: Commit the permanent eval case**

```bash
git add tests/evals/measurement_cases/messy_english.yaml tests/evals/measurement_eval_harness.py
git commit -m "test(chat): cover issue 336 opening asset"
```

- [ ] **Step 7: Reconcile integration and publish the Draft PR**

Fetch `origin/codex/private-alpha-next`, compare it with the original base `6533377c1a08539136a622a7d53eee20d0efd845`, and merge the current integration branch into this worker only if it advanced. Audit semantic overlap before retaining or rerunning evidence. Push `codex/issue-336-opening-asset-continuity`, open a Draft PR targeting `codex/private-alpha-next`, include `Closes #336`, apply relevant existing labels, and wait for exact-head CI. Do not merge the PR.
