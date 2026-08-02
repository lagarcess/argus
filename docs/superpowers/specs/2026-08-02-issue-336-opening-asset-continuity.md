# Issue #336 Opening-Turn Asset Continuity

Recognize a company named in a terse opening backtest request without asking for the asset again.

Founder-locked 2026-08-02 through GitHub issue #336 and the locked G-01 checkpoint evidence.

## 1. Why

Argus's first successful backtest is the activation milestone, and the product contract says to ask only what improves the next useful response. The opening request `let's test apple with 10K` already supplies the asset and starting capital. Re-asking for the asset adds avoidable Golden Path friction.

Authority:

- `docs/PRODUCT.md` sections 5 and 20 make ordinary chat and the first backtest the Golden Path.
- `docs/API_CONTRACT.md` section 1 says to derive available facts through conversation and ask only for genuinely missing information.
- `docs/reports/2026-08-01-current-checkpoint-experience-feedback.md` G-01 records the reproduced failure and locks the correct date clarification as separate, valid behavior.

## 2. Locked decisions

1. The opening turn `let's test apple with 10K` must preserve Apple as the traded asset and canonicalize it to `AAPL` through provider-backed resolution.
2. The same turn must preserve `10000` as starting capital.
3. Because the turn supplies no date window, Argus must ask only for the missing period; it must not claim the draft is executable.
4. The fix stays LLM-first. Post-LLM reconciliation may correct stale typed state only from provider-owned resolution facts; it must not add regexes, localized aliases, company-name tables, or an early deterministic route.
5. The regression becomes a typed live-eval case that asserts asset, capital, missing-period clarification, and stage outcomes rather than exact prose.
6. Existing provider-backed canonicalization and clarification owners remain unchanged.

## 3. Reserved / parked scope

- G-01's `the year so far` date interpretation is excluded because issue #336 explicitly marks the missing-date clarification behavior as correct for this reproduction.
- Stale attention state is owned separately; this lane does not change conversation activity or minimap behavior.
- No frontend, API, database, market-data provider, model-selection, or quota change is included.
- No broad interpreter refactor or generic prompt rewrite is included.

## 4. Contract gates

- `docs/API_CONTRACT.md` -- no shape change; existing LLM-first extraction and missing-field semantics remain authoritative.
- `docs/DATA_MODEL.md` -- no change.
- OpenAPI -- no change.
- `tests/evals/measurement_cases/messy_english.yaml` -- add the exact issue #336 typed acceptance case.

## 5. Execution contract

- **PR shape:** one focused PR targeting `codex/private-alpha-next`, with a spec commit followed by the test-first implementation commit(s).
- **Proof required before the PR counts as ready:** focused red/green tests for the typed provider-context reconciliation contract and exact eval fixture; provider-free agent-runtime and mocked eval gates; the hermetic interpreter regression sweep; one sanctioned full live eval on the exact PR head, including the new issue #336 case; proportional code review; exact-head GitHub CI.
- **Where it stops:** a Draft PR ready for founder review. The founder merges. This lane does not deploy, promote, or expose testers.

## 6. Stop conditions

- If the exact case requires a deterministic scan of the user's text, a localized alias, or a company-name lookup before LLM extraction, stop and report.
- If Apple resolves ambiguously or cannot be validated by the existing provider-backed catalog, stop and report rather than hardcoding `Apple -> AAPL`.
- If the smallest fix changes date interpretation, model routing, provider selection, API/data contracts, or frontend behavior, stop and report the scope expansion.
- If the exact live case still re-asks for the asset after the bounded typed provider-context reconciliation, stop and bring back the typed outcome and route-receipt evidence before adding another repair layer.

## Sources

### Argus authority

- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `.agent/designs/argus/DESIGN.md`
- `docs/specs/private-alpha-next-roadmap.md`
- `docs/specs/private-alpha-next-decision-memo.md`
- `docs/reports/2026-08-01-current-checkpoint-experience-feedback.md`
- GitHub issue #336

### External inspiration

- None.

### Inference

- Code inspection shows that provider-context normalization canonicalizes a resolved company name, but previously left the model's stale `asset_universe` missing-field blocker and asset-question prose intact. The bounded failure surface is post-LLM reconciliation of that stale typed state from provider-owned facts. The exact-head live gate must confirm that this diagnosis fixes the observed path without changing natural-language interpretation.
