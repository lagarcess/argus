# The registry: executable tool declarations

Execution contract for the founder's 2026-09-09 registry kickoff. Requirements
remain `docs/reports/lift-loop-lane-c/README.md`, especially sections 3 and 4,
and `docs/specs/argus-grounded-finance-roadmap.md`, The registry and rules 2–8.

## Why

Argus must compute or cite its answers. A catalog describes actual operations,
not question categories. PR #567 removed the strategy catalog from neutral
envelope imports; this lane supplies the declaration and its real consumers.

## Locked decisions

1. Each declaration owns identity, description, a real callable with a typed
   argument model and return model, cross-argument rules, units/domain facts,
   failure semantics, execution cost/confirmation policy, a locale-key progress
   template with typed fact interpolation, and a versioned card binding.
2. Argument schemas derive from the callable's annotated argument model. There
   is no universal calculation input model. An optional trusted execution
   context is injected by the runtime and is never model-authored input.
3. Exactly-one-unknown rules count `None`, never falsiness. Field/domain
   validation and cross-argument rules apply before dispatch and recompute.
4. The model reads a generated catalog and emits zero or more ordered calls
   with distinct call IDs. Two tools and repeated calls to one tool remain
   expressible. No question-shape-to-tool mapping is introduced or retained as
   the owner of the new route.
5. Canonical task intents become `explain`, `calculate`, `follow_up`, `cannot`.
   Old persisted intent spellings normalize at compatibility read boundaries;
   presentation intents such as `beginner_guidance` are separate and keep
   their existing meaning. Strategy ownership derives from actual tool/typed
   strategy data, never the new general `calculate` label alone.
6. Existing backtest and five research execution classes consume this catalog.
   Provider implementations, metering and backtest launch validation retain
   their ownership. Strategy-template unsupported admission remains strategy
   specific. Capability answers and model-facing catalog text derive from the
   same declarations and executable strategy data.
7. Policy is consumed before constructing a backtest launch payload. Free,
   local, unambiguous calls execute and answer immediately. Backtest calls keep
   confirmation, durable admission and worker execution. Shared outcomes
   distinguish success, invalid, ambiguous, bounded and unavailable results;
   a failure cannot carry an answer disguised as success.
8. A neutral `ToolCall` transport carries `tool_name`, `call_id` and arguments;
   the model-facing schema specializes arguments per declaration. A
   `ToolResultCard` envelope carries kind/version, tool/call/artifact identity,
   input revision, card binding, arguments, typed outcome and presentation.
   A `ToolCardPresentation` contains display facts and units, not a universal
   input or financial result schema.
9. The declaration's presenter supplies the card facts. A shared second card
   component renders these facts; a new calculation does not require another
   central frontend map entry. Receipts render the same presentation. Existing
   receipt version 1 remains readable; a new version publishes only sanitized
   presentation and binding, never private call IDs or raw execution records.
10. Progress is emitted at actual invocation using the existing event channel.
    Graph stages retain operational meaning but cease to select product copy.
    Delete the seven stage-keyed status strings. No progress model call.
11. Recompute retains the unknown, validates editable fields, increments the
    input revision, and persists inputs/outcome/presentation together through
    the existing guarded message-artifact writer. A stale revision loses
    before execution where detectable; a racing stale write cannot replace a
    newer result. Shared liveness, retry supersession and continuity remain
    shared owners rather than per-tool branches.

## Reserved scope

- No production calculator, prototype promotion, universal input schema,
  question classifier, financial advice, new service, deployment, migration
  application, merge, or sharing-flag activation.
- Serializer-pinned classes in `agent_runtime/state/models.py` never move or
  rename. `EditOperation.target` is not widened into a calculation schema.
- Test-only typed identity/echo functions prove invocation and failures; the
  Lane C mathematical prototype remains inspection-only.

## Contract gates

- `docs/ARCHITECTURE.md`: registry, policy dispatch, and result ownership.
- `docs/API_CONTRACT.md`: tool progress, result/card transport, recompute and
  receipt versioning; backend and frontend types evolve together.
- `docs/DATA_MODEL.md`: message-owned tool results and guarded revisions.
- `.agent/designs/argus/DESIGN.md`: answer-first inputs and actual-call progress.
- Interpreter fingerprint includes generated catalog and schema facts, backed
  by a committed full-suite scorecard; enum changes cannot evade measurement.

## Execution contract

- One non-draft worker PR targeting `codex/private-alpha-next`; labels
  `enhancement`, `core`, `api`, `code health`. Founder merges and deploys.
- Original fetched integration base:
  `9e8b59b23f29d432ec7603c42f7362137b1ee21f`. Initial reconciliation is a no-op.
- Focused failing-then-passing declaration/runtime/lifecycle/presentation tests;
  mocked eval harness; Lane C's 31 fresh-process probes; lint/type checks;
  durable English/es-419 browser evidence, including a non-buy-and-hold
  backtest where the changed surface depends on strategy shape.
- Historical Lane C currently fails three lifecycle subprocesses because Lane
  B moved `_stamped_card_metadata`. Migrate only that probe to the canonical
  shared stamper with its explicit historical layout fixture, preserve the
  original evidence JSON, and record new observations separately.
- Intent/catalog changes are broad: run all 68 live cases after deterministic
  checks. Estimated reported provider cost is $1–2 for one run, based on PR
  #565's $1.11 reported cost with some missing receipt prices; this is not a
  hard cap. State any additional paid rerun cost before running it.
- Before readiness: fetch/reconcile integration one-way, assess semantic
  overlap, run modularity on the would-be merged tree, retain/revalidate exact
  head evidence, require terminal CI, completed Codex review naming current
  head and zero unresolved threads. A draft PR is never clear.

## Stop conditions

Stop and report if meeting these requirements would require a named-question
classifier, pretending a calculation is a backtest, moving serializer-pinned
classes, promoting the prototype, duplicating monetary math in the browser,
or changing founder-owned deployment/sharing authority. Do not waive a
confirmed correctness or durable-state requirement to fit the file list.
