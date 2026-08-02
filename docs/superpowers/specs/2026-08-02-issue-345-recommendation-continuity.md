# Result-card recommendation continuity

Result-card recommendation follow-ups preserve the source run's canonical owned
facts while changing only the experiment field named by the selected row.

Founder-locked 2026-08-02 through GitHub issue #345, after the 2026-08-01
current-checkpoint experience review recorded S-09 and S-11.

## 1. Why

Argus's Golden Path ends by suggesting what to test next, and the product
decision filter asks whether a change helps a normal person continue a grounded
investing experiment. A recommendation that loses modeled costs or falls back
to generic guidance breaks that loop and makes the next experiment less
trustworthy than the result it came from.

This lane enforces the existing conversation-artifact continuity contract in
`docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`, and `docs/DATA_MODEL.md`: build a
follow-up draft from canonical run state, apply the selected recommendation as
a narrow patch, and leave the completed source run immutable.

## 2. Locked decisions

1. A result-card recommendation follow-up is anchored to the completed source
   run's canonical configuration, never reconstructed from display prose.
2. Every still-applicable owned fact carries forward unless the recommendation
   explicitly changes it: assets, capital, date window, timeframe, benchmark,
   fees, slippage, and their provenance.
3. `compare_buy_and_hold` changes the strategy semantics from the source DCA
   setup to buy and hold while preserving all other applicable owned facts.
4. `change_date_range` changes only the date window selected or interpreted for
   the follow-up; it must preserve modeled fees, slippage, and benchmark cost
   parity.
5. A valid recommendation follow-up produces the ordinary new confirmation
   artifact. Generic Try next guidance must not replace that confirmation.
6. The completed source result remains immutable and visible as history; the
   new confirmation becomes the active artifact.
7. Both behaviors require regression tests that fail against the pre-fix code
   for the intended continuity reason before production code changes.
8. The implementation must be the smallest safe correction at the shared
   recommendation/continuity boundary. If diagnosis proves separate causes,
   each correction remains bounded to its verified cause.

## 3. Reserved / parked scope

- User-typed compound edits and the shared conversational edit contract --
  issue #345 explicitly covers recommendation-generated follow-ups, not #339's
  edit-contract surface.
- New recommendation kinds, ranking, labels, or recommendation-generation
  policy -- the existing `argus_next_experiments/v1` taxonomy remains intact.
- Historical run mutation or backfill -- old results remain immutable.
- Database schema, RLS, migration, hosted configuration, provider selection,
  and deployment -- none is needed for this continuity correction.
- Generic Try next redesign -- only the confirmed leakage reachable from the
  two issue reproductions is in scope.

## 4. Contract gates

- `docs/API_CONTRACT.md` -- no shape change expected; the existing Structured
  Action Semantics and Conversation Artifact Continuity Contract are the gate.
- `docs/DATA_MODEL.md` -- no schema change expected; the existing immutable
  `backtest_runs.config_snapshot` and result-follow-up seeding rules are the
  gate.
- `docs/ARCHITECTURE.md` -- no architecture change expected; LangGraph remains
  the only chat brain and canonical artifacts own durable facts.
- `docs/api/openapi.yaml` -- regeneration is not required unless diagnosis
  unexpectedly proves a public schema change is necessary, which is a stop
  condition.
- `docs/reports/2026-08-01-current-checkpoint-experience-feedback.md` -- locked
  evidence source; do not edit it.

## 5. Execution contract

- **PR shape:** one worker PR targeting `codex/private-alpha-next`, containing
  this spec, focused failing-first regressions, the smallest shared-boundary
  correction, and bounded evidence. The recorded integration base is
  `6533377c1a08539136a622a7d53eee20d0efd845`.
- **Proof required before the PR counts as ready:** focused unit/runtime tests
  for DCA to buy-and-hold and a modeled-cost date-range recommendation; the
  hermetic agent-runtime regression gate if `agent_runtime/` changes; relevant
  backend/frontend checks for touched surfaces; English and Latin American
  Spanish browser QA for the recommendation-to-confirmation flow; and
  screenshot evidence that modeled fees and slippage survive the date-range
  recommendation. Live/provider-backed gates may run only when the repository
  release discipline requires them and the configured environment is valid.
- **Review required:** independently map every locked decision to the exact
  code and test evidence, verify the source run remains unchanged, confirm the
  diff does not alter the typed user-edit contract, and complete mandatory
  pre-merge review.
- **Where it stops:** an open Draft or posted PR with exact-head evidence and
  terminal CI reported. The founder merges. This lane does not merge, deploy,
  promote, or apply hosted state.

## 6. Stop conditions

- If the smallest safe fix requires changing the public API schema, OpenAPI
  shape, data model, RLS, or a migration, stop and report to the founder.
- If diagnosis requires changing the shared user-typed conversational edit
  contract or resolving issue #339 in this lane, stop and report to the
  founder.
- If preserving facts would require mutating a completed run, rebuilding facts
  from frontend prose, or adding a second runtime/NLU path, stop and report.
- If the two reproductions require a new product decision about what a
  recommendation means, rather than enforcing the locked issue behavior, stop
  and report.
- If required browser or interpreter-facing live proof cannot run safely from
  the configured environment, publish only if the issue and release contract
  allow a Draft with that gate explicitly open; otherwise stop before a READY
  claim.
- If current `origin/codex/private-alpha-next` advances with semantic overlap in
  recommendation generation, artifact continuity, execution-cost state, or
  directly affected tests, reconcile one-way and re-audit the affected proof
  before readiness.

## Sources

### Argus authority

- `docs/PRODUCT.md` sections 19-21: result trust, Golden Path, and product
  decision filter.
- `docs/ARCHITECTURE.md` section 11: Conversation Artifact Continuity.
- `docs/API_CONTRACT.md`: Structured Action Semantics and Conversation Artifact
  Continuity Contract.
- `docs/DATA_MODEL.md` sections 8 and 12: canonical artifact reconstruction,
  immutable runs, and result-card follow-up seeding.
- `.agent/designs/argus/DESIGN.md` sections 11-12: next-move rows and result-card
  trust.
- `docs/specs/private-alpha-next-roadmap.md`: result-surface ownership and
  modeled-cost preservation baseline.
- `docs/reports/2026-08-01-current-checkpoint-experience-feedback.md` S-09 and
  S-11.
- GitHub issue #345.

### External inspiration

- None. This is enforcement of an existing Argus-owned continuity contract.

### Inference

- The two screenshots may share a recommendation-acceptance boundary, but the
  root cause is intentionally left unassumed until both paths are traced.
