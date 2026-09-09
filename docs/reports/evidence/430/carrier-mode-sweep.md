## Carrier-mode sweep before the fix

Baseline: founder head `34f3ad4592e655fca6c2efa9897918decc8c5e09`.

Confirmed owner: `artifact_edit_outcomes.py:159`, shared by normal response and all recovery entry points. It compares a legacy asset patch with a resolved final basket and discards the legacy append/add mode.

- Typed replace MSFT, legacy append/add MSFT, current AAPL: final baskets MSFT versus AAPL+MSFT; no receipt before the fix.
- Typed remove MSFT, legacy append AAPL, current AAPL+MSFT: final baskets AAPL versus AAPL+MSFT; no receipt before the fix.
- Typed add MSFT, legacy append MSFT, current AAPL: both yield AAPL+MSFT; false conflict before the fix.

No second mode-blind carrier equality was found. The primary-vs-plan asset coverage at `artifact_assumption_edit.py:1068-1128` checks modes and final membership; its change detector at 1315-1329 expands append against current. Asset sequence resolution keeps operation ordering; same-target primary completion is checked by materialized coverage. All other legacy-map targets have scalar assignment semantics, with set/replace true aliases; benchmark clear and unsupported scalar modes retain their existing handling. Date/indicator/family targets have no legacy flat carrier in this map. Independent deterministic sweep: 21 checks passed, including ordered and inverse operations, mixed refusal, set/replace aliases, and primary append versus planned replace.

Fix scope: project legacy asset intent through `apply_asset_universe_edit` against the same current basket as the typed resolver, then compare final normalized baskets. Preserve one owner for asset semantics, one owner for conflict disclosure, and no model-facing edits.

## Red/green proof

Before the fix, 14 normal/recovery card-path cases failed and 17 controls passed in `test_edit_carrier_conflicts.py`. Missing receipts reproduced for replace versus append/add, remove versus append, and a remove/add sequence versus append; false receipts reproduced for equivalent add/append and replacement/append baskets. The 18 new card-path variants now pass alongside the prior controls. The focused edit suite passes 118 tests. The complete local agent-runtime plus spine sweep passes 2,119 tests with CI defaults; the first local run had two failures caused by the worktree research flag, and all 21 affected-file tests passed after restoring the default. The mocked/freeze suite passes 246 tests.

The shared disclosure owner now applies the legacy asset carrier through the existing `apply_asset_universe_edit` owner against the current basket supplied by each adapter. The typed resolver already returns the final basket. The normal callee supplies `_current_artifact_asset_universe(request)`, the same owner used by its typed resolver; recovery supplies the same `prior_strategy.asset_universe` used by its resolver. Modes and aliases remain owned by the existing asset function, without adding model-facing fields or changing the planner.

## Integration and process

This follow-up starts from founder head `34f3ad4592e655fca6c2efa9897918decc8c5e09`, retaining the founder's merge and roadmap conflict resolution. That head includes #565, #567 and #568. #565 overlaps interpreter routing/admission; #568 overlaps streamed/persisted web message projection; #567's schema import overlap was previously verified. Focused card-path tests, the full agent-runtime gate and bilingual browser replay cover the affected surfaces. No live eval is owed because this worker changes no model-facing text or schema.

The earlier draft-era terminal report overstated readiness: the ready transition triggered another review and enabled the agent-runtime sweep. The PR remains non-draft. Final completion requires green CI including that sweep at the final head, a clean Codex round at that head, zero unresolved review threads, and a replacement terminal audit written afterward.

The extended controlled browser spec passes 16 cases. Eight new EN/es-419 live/reload screenshots cover the conflicting and equivalent carrier outcomes; the previous 16 screenshots match byte-for-byte. All 10 original card fixtures and IDs are unchanged. Final-head replay and hosted CI/review results belong in the replacement terminal audit.

## Canonical starting-basket follow-up

The next exact-head Codex round found a valid P2 in this fix: the legacy asset function normalizes its patch but retains base spelling, whereas the typed resolver normalizes its starting basket. Four adapter-level regressions (main/recovery, dash form and a spaced/duplicate alias form) reproduced false conflict receipts for equivalent adds. The shared disclosure owner now passes the starting basket through the same `normalized_asset_symbols` owner used by the typed resolver. This covers case, spacing, dash/slash aliases and deduplication without adding symbol exceptions or changing the existing application function. Both carriers now start from the same canonical basket.

These alias regressions assert both adapters' structured output directly, avoiding the simplified browser/card helper's instrument classification for share-class symbols. The full card-path matrix and bilingual browser cases continue to cover operation modes and visible receipts. The final audit will record exact-head retesting and the subsequent Codex outcome. Integration advanced only by the roadmap's canary-provision-flake note (`73949fdf`); it changes no runtime, API, UI, migration, environment or test owner.
