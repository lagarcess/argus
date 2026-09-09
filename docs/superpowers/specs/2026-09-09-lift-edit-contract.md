# Lift the pending-artifact and edit contracts

Lane B from `docs/specs/argus-grounded-finance-roadmap.md`, including #430.
Execution of the founder's 2026-09-08 request; one worker PR.

## 1. Why

Operating rule 1 requires one owner for general contracts that grew inside the
backtest. An edit must apply every requested change or explicitly disclose what
did not apply. #430 exposes a silent third outcome when a planner returns no
operations and no note. Product truth requires answers users can check.

## 2. Locked decisions

1. Extract pending-artifact liveness, state stamping and guarded mutation into
   reusable functions parameterized by artifact metadata layout and adapter
   callbacks. Backtest content, launch admission and checkpoint model projection
   stay in backtest adapters. Preserve existing public imports and behavior.
2. Extract edit-outcome accounting/disclosure into a shared module that does not
   import the backtest planner, strategy catalog or model-facing schemas. Feed it
   materialization facts from the existing callee. The planner remains unchanged.
3. An edit that materializes nothing has a typed disclosure even when the planner
   extracted nothing. Do not infer the intended field from prose. Client copy
   honestly says no changes were applied and asks for a restatement.
4. Audit all routes through materialization and card re-issue, including ready,
   clarification and unsupported planner outcomes, discarded operations and
   legacy flat fields. Add focused tests for every reachable silent path found.
   Preserve the already-correct typed-operation refusal and asset extraction.
5. New web confirmation cards emit `kind: "backtest"`. The client boundary
   normalizes missing legacy kinds to backtest and dispatches by the discriminator;
   explicit unknown kinds must not masquerade as backtest cards.
6. The disclosure envelope is shared; target-specific labels remain backtest
   presentation. `unapplied` entries retain `{op, target, reason}` and optional
   `note`. A generic empty application uses `op: "edit"`,
   `target: "requested_change"`, `reason: "no_change_applied"`.

## 3. Reserved / parked scope

- No second calculation, universal input schema, result-body generalization,
  strategy provenance redesign, dispatch registry or hosted changes.
- No model-facing text/schema changes, planner prompt edits or live evaluation.
- No edits to `llm_interpreter.py`, or interpreter `capability_context_audits.py`,
  `discovery_focused_read.py`, `focused_extraction.py`, `research_routing.py`.
- Do not widen `EditOperation.target`, move checkpoint classes in `state.models`,
  or change `api/state.py` serializer class paths.

## 4. Contract gates

- `docs/API_CONTRACT.md`: additive card discriminator and generic edit disclosure.
- `docs/CONVERSATIONAL_RUNTIME.md`: replace the obsolete empty-plan limitation
  with the actual deterministic boundary, without claiming to recover unseen
  parts of a partially understood request.
- No table or checkpoint schema migration. OpenAPI regeneration only if a
  registered Pydantic API schema changes.

## 5. Execution contract

- One PR targeting `codex/private-alpha-next`, closing #430 on merge; labels
  `bug`, `refactor`, `core`, `web`. Founder retains merge/deploy authority.
- Original fetched integration base: `3738fbec0bd4f96c0248abc52e6b2e2287a8c69c`.
  This includes requested `6fa3f55a`; the intervening commit updates board status.
- Test-first focused backend lifecycle and edit regression suites, frontend
  discriminator/hydration/disclosure tests, mocked eval harness, lint/type checks.
- Durable browser screenshots for English and es-419, covering empty application,
  typed refusal, successful editing and both buy-and-hold and recurring inputs.
  Use controlled planner output for the variance regression; identify fixtures
  honestly. No live eval is owed or authorized by this lane.
- Preserve fingerprint bytes and directly verify unchanged model-facing files
  and planner prompt/schema (the fingerprint alone cannot prove these).
- Fetch/reconcile before final evidence. Run modularity budget on the merged
  tree. Exact-head green CI, Codex round cleared at that head, zero unresolved
  threads; terminal audit only after review returns.

## 6. Stop conditions

- A needed fix crosses any forbidden file or model-facing surface above.
- A confirmed reachable silent edit cannot be closed within the callee/shared
  extraction without changing the protected caller: report evidence and stop.
- Any need to change hosted state, merge or deploy requires founder direction.

## Baseline findings

At the fetched base, `.agent/modularity_budget.json` watches
`artifact_assumption_edit.py`: baseline 1,489, allowed growth 75, actual 1,561,
limit 1,564, remaining 3. The board's count is current. `llm_interpreter.py`
has 5,335 lines against limit 5,354, leaving 19. Neither budget is widened.

## Implementation sequence

- [x] Reproduce and inventory silent edit outcomes with focused failing tests.
- [x] Extract lifecycle with a second metadata layout proving parameterization;
  retain backtest adapter compatibility and existing lifecycle suites.
- [x] Extract shared edit completion/disclosure, close reachable silent paths
  in the callee, shrink the watched interpreter module.
- [x] Add card discriminator and bilingual generic disclosure at hydration/render.
- [ ] Run focused and mocked verification, browser acceptance, reconcile,
  merged-tree budget, PR CI and scoped Codex review; record terminal evidence.

## Sources

- `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`
- `docs/specs/argus-grounded-finance-roadmap.md`, operating rule 1 / Lift the loop
- `docs/specs/private-alpha-next-decision-memo.md`, language/runtime spine
- Issue #430 and its founder comment; PR #565 current changed-file inventory
