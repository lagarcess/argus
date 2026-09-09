# Lift the loop, Lane C: throwaway proof

**NEVER MERGE THIS BRANCH. The deliverable is this report.**

The calculation reaches loose message, reference and result containers with its
own five inputs. It does **not** reach a reusable, backtest-independent loop.
Lane A relocated code; several consumers still import the backtest bodies, and
some apparently neutral imports still load the strategy catalog. No missing
adapter was built to disguise those boundaries.

Examined integration base: `6bc3e0ee84fef9911230cec496734edc29f640a9`.
That was also the remote integration SHA when checked. It contains Lane A,
`f7c9192b94efb974108c00d20d8cc30e9154faf1` / PR #560. No reconciliation was
needed or performed. All additions are in this report directory; no runtime,
web, deployment, schema, dependency or interpreter file changed.

The controlling board is [the primitives table](../../specs/argus-grounded-finance-roadmap.md#L102-L117),
[rules 2, 3 and 8](../../specs/argus-grounded-finance-roadmap.md#L265-L296), and
[Lane C](../../specs/argus-grounded-finance-roadmap.md#L429-L494).

## The experiment and its limits

One function, `solve_for_unknown(present_value, payment, rate, periods,
future_value)`, accepts exactly one `None`. Zero remains a known value. Its
[implementation and conventions](compute.py#L1-L71) use signed ordinary-annuity
cash flows:

`PV × (1+r)^n + PMT × annuity_factor(r,n) + FV = 0`.

Payments occur at each period's end. Rate is effective per payment period.
All monetary amounts share one currency; no exchange-rate or APR conversion is
implied. The two requested shapes are just values in a parameterized test:

| Inputs, in signature order | Solved answer | Interpretation |
| --- | --- | --- |
| `(0, None, 0, 12, 12000)` | payment = `-1000` | A savings goal requiring 1,000 paid each period. |
| `(None, -1000, 0, 12, 0)` | present value = `12000` | An amount supported by twelve payments of 1,000 at zero interest. |

The negative payment means money paid out. These are arithmetic examples, not
prescriptions. There are no product names, scenario identifiers, text matching,
or question-specific branches in the implementation or fixture selection.
[The same-call test](test_proof.py#L42-L50) and
[transport probe](test_proof.py#L131-L165) exercise both shapes. Every one of the
five blanks is also checked against an independent, period-by-period cash-flow
oracle at zero, positive and negative rates
([tests](test_proof.py#L12-L39)).

Rate inversion deliberately requires integer periods and exactly one cash-flow
sign change; its bounded search is `-30 <= log(1+r) <= 30`. Multiple-sign-change
flows are rejected rather than choosing a possibly ambiguous root. Other
inversions accept positive fractional periods as an algebraic equivalent,
without claiming a partial-payment schedule. Undefined or nonfinite answers
raise `ValueError`. This is bounded annuity math, not a production amortization,
irregular-cash-flow or DCF engine. See [rate inversion](compute.py#L74-L118) and
[boundary tests](test_proof.py#L73-L104). There is no provider, graph, route,
interpreter, UI or live recomputation implementation.

## 1. Which envelopes were reachable?

The harness uses **31 fresh-process probes**. A body guard refuses imports of
`argus.domain.backtesting`, `argus.domain.engine_launch`, and
`argus.agent_runtime.strategy_contract`. A second guard also refuses
`argus.domain.strategy_capabilities`. An observation run allows imports and
records every loaded Argus module. A network audit guard refuses connections.
These are import failures, not stubbed successes. The lifecycle write is only
called with the body guard, which stops it before any persistence code can run.
See [guard implementation](test_proof.py#L348-L379),
[probe matrix](test_proof.py#L382-L450), and [raw observations](evidence.json).

“Passes the body guard” below is deliberately narrower than “imports no
backtest code.” The full dependency lists expose that distinction.

| Envelope / surface | Observed result | Source of the remaining dependency or shape requirement |
| --- | --- | --- |
| Message metadata, `ArtifactReference`, `FinalResponsePayload.result` | Both answers and their exact inputs survive real Pydantic JSON round trips, without a strategy, symbol, date range or run id. Passes body guard; fails catalog guard. | The containers are open ([Message:315-321](../../../src/argus/api/schemas.py#L315-L321), [reference:252-256](../../../src/argus/agent_runtime/state/models.py#L252-L256), [final:324-331](../../../src/argus/agent_runtime/state/models.py#L324-L331)). But [runtime package imports:3-34](../../../src/argus/agent_runtime/__init__.py#L3-L34) load state models; [models:16](../../../src/argus/agent_runtime/state/models.py#L16) loads the strategy registry, which [imports the catalog:20-26](../../../src/argus/domain/capability_registry.py#L20-L26). `api.schemas` independently imports that registry and the backtest reader projection ([schemas:22-30](../../../src/argus/api/schemas.py#L22-L30), [reader:15-16](../../../src/argus/api/artifact_presentation.py#L15-L16)). Structurally reusable, not dependency-independent. |
| Pending artifact lifecycle | Module import and metadata stamping pass both guards. Stamping a `calculation_card` leaves it unchanged; the same helper stamps only `confirmation_card`. Calling the real update fails on a backtesting import. | The envelope keys are fixed ([stamping:43-59](../../../src/argus/api/chat/confirmation_lifecycle.py#L43-L59)). The writer imports confirmation validation, artifact context and the backtest card builder, then forces `await_approval` and `conversation_mode=confirm` ([writer:393-440](../../../src/argus/api/chat/confirmation_lifecycle.py#L393-L440)). The builder requires `strategy` ([builder:94-101](../../../src/argus/api/chat/confirmation.py#L94-L101)); launch validation requires `LaunchBacktestRequest` ([validation:18-44](../../../src/argus/agent_runtime/confirmation_artifacts.py#L18-L44)). |
| Edit disclosure carrier | `ConfirmationPayload` refuses the TVM input object: required field `strategy` is missing. No empty strategy was inserted to make it pass. | `edit_disclosure` is an open dict inside a mandatory backtest-shaped payload ([models:310-317](../../../src/argus/agent_runtime/state/models.py#L310-L317)). Its web entry type has generic `op/target/reason` strings, but is a property of the strategy confirmation ([types:212-238](../../../web/components/chat/types.ts#L212-L238)); `ChatMessage` reads it from `message.confirmation` ([reader:306-309](../../../web/components/chat/ChatMessage.tsx#L306-L309)). |
| Applied / unapplied bookkeeping | With imports allowed, the existing helpers carry `set.payment` / `set.rate`, detect a partially materialized edit and produce a typed `unsupported_operation` disclosure. Body-guarded import fails. Creating an actual `EditOperation(target="payment")` fails validation. | The planner still imports interpreter and backtest rule code ([imports:10-33](../../../src/argus/agent_runtime/artifact_edit_planner.py#L10-L33)); its bookkeeping is embedded at [612-713](../../../src/argus/agent_runtime/artifact_edit_planner.py#L612-L713). The model-facing target vocabulary remains fixed at [43-58](../../../src/argus/agent_runtime/artifact_edit_planner.py#L43-L58). Manually populating its bookkeeping strings is evidence about the bookkeeping only, not a working TVM edit. |
| Try next row contract | Open offered-kind metadata retains `solve_for_unknown`; the label-key helper can form a key. Body guard passes, catalog guard fails through package initialization. The existing structured continuity resolver returns `None` for this kind. | [Row helpers:119-160](../../../src/argus/agent_runtime/next_experiments_contract.py#L119-L160) remain distinct from the backtest composer. The web row envelope accepts a string kind and label fields ([web parser:34-45,66-94](../../../web/lib/chat-next-experiments.ts#L34-L94)), but structured continuity is still `refine_strategy` plus source run id for two enumerated kinds ([action:150-164](../../../web/lib/chat-next-experiments.ts#L150-L164)). A syntactically generated label key does not create copy, compose a useful next move, or execute a tool. |
| Typed facts to client copy | `ResponseIntent.facts` retains the five values under an existing intent. A new `kind="calculation"` is rejected. The real confirmation projector given unrenamed TVM values returns `{}` and requires body imports. | The fact dict is general, its intent vocabulary is not ([models:44-55,236-241](../../../src/argus/agent_runtime/state/models.py#L44-L241)). The projector imports backtest config and reads capital/cadence/cost/benchmark facts ([facts:7-65](../../../src/argus/agent_runtime/confirmation_facts.py#L7-L65)); the client consumes that same backtest vocabulary ([client:11-102](../../../web/lib/confirmation-assumptions-display.ts#L11-L102)). No TVM values were renamed to capital or fees. |
| Result presentation / hydration | The classifier imports cleanly, but returns `None` for `calculation_card`. Putting an empty dict under `result_card` classifies it as a result. That is key recognition, not TVM support. | The classifier knows only result/breakdown/assumptions/confirmation ([classifier:6-40](../../../src/argus/domain/artifact_presentation_kind.py#L6-L40)). The real web hydration guard requires title, status label, rows, assumptions, actions and a date range ([hydration:400-416](../../../web/lib/chat-message-hydration.ts#L400-L416)). The proof card has its own answer and inputs; it is not a rendered result card. |
| Retry supersession (adjacent lifecycle check) | A newly computed TVM artifact leaves a prior retry `active`. Body guard passes, catalog guard fails. | Superseding artifact kinds enumerate confirmation/backtest result/saved strategy/cancelled confirmation ([lifecycle:15-41](../../../src/argus/agent_runtime/artifacts/lifecycle.py#L15-L41)). A new result kind needs shared lifecycle semantics, not another per-calculation special case. |

Thus the pure stamping helper is import-clean but confirmation-shaped; the
presentation classifier is import-clean but does not recognize the calculation.
The useful open containers are engine-free, with the named catalog/reader
coupling still present. **The strict “reach the loop without backtest imports”
claim is not established.** Relocation alone did not make that claim true.

## 2. How many artifacts did it actually take?

**Four runnable proof artifacts; six committed files in total.** The two extra
files are this report and its raw evidence. There is no fifth executable
adapter hidden in the prototype.

| Artifact | Responsibility |
| --- | --- |
| [declaration.py:10-20](declaration.py#L10-L20) | One local tool declaration, pointing to the compute function and card body, plus its cost and unit conventions. It registers nothing in Argus. |
| [compute.py:11-118](compute.py#L11-L118) | Five-argument solver and its private mathematical rate-inversion helper. |
| [test_proof.py:12-511](test_proof.py#L12-L511) | Unit harness, independent arithmetic oracle, import probes and evidence capture. No separate runner, fixture package, conftest or dependency was added. |
| [card.py:4-11](card.py#L4-L11) | Plain typed card body: answer first, original inputs underneath. No rendered component or edit callback. |
| [README.md](README.md) — extra | The requested written findings and registry requirements. |
| [evidence.json](evidence.json) — extra | Durable raw import/results evidence and hashes of the four Python files. |

**This does not pass rule 3's product-level four-artifact bar.** Only the local
calculation and payload proof fit four runnable artifacts; neither a real
product card nor the complete loop was built. Counting this as a successful
four-artifact calculation addition would conceal the absent work.

Using the current loop would additionally require changes at these existing
owners: dispatch, pending-card assembly/update, edit application/disclosure,
fact projection/localization, result selection/hydration, and retry/continuity
semantics. Their concrete blockers are in the table above and section 3. They
are **unbuilt requirements**, not six invented adapters or a measured count of
future files. The registry lane must absorb the shared work so each subsequent
calculation does not pay for those owners again. Do not use this spike to waive
the board's stop condition before calculation four.

## 3. What is missing for answer first, editable inputs, live recompute?

1. **Cost-based dispatch into a calculation.** The declaration can say
   `answer_first`, but nothing in Argus consumes it. The graph supplies one
   backtest tool and named confirm/execute nodes
   ([workflow:149-206](../../../src/argus/agent_runtime/graph/workflow.py#L149-L206)).
   Execute always builds a launch payload before calling the tool
   ([execute:50-71](../../../src/argus/agent_runtime/stages/execute.py#L50-L71)).
   A cheap calculation needs a validated compute-and-answer path selected by
   tool policy. Making it pretend to be an approved backtest would add the very
   confirmation friction rule 2 rejects.
2. **A recognized calculation card with units and a retained unknown.** The
   current result guard requires historical date-range chrome; confirmation
   rows and editable capabilities enumerate strategy fields
   ([types:166-173,257-280](../../../web/components/chat/types.ts#L166-L280)).
   TVM needs to retain which input is unknown while editing the other four,
   distinguish zero from blank, and present per-period rate/payment units.
   The proof preserves those facts in a payload; it supplies no UI behavior.
3. **A no-turn recompute operation.** Current direct edits require a canonical
   strategy and launch payload, make `EditOperation`s and call confirm again
   ([direct edit:17-59](../../../src/argus/agent_runtime/confirmation_direct_edit.py#L17-L59)).
   The drawer offers capital/dates/costs and explicitly submits an Apply action
   ([drawer:160-188](../../../web/components/chat/ConfirmationDirectEdit.tsx#L160-L188),
   [submit:229](../../../web/components/chat/ConfirmationDirectEdit.tsx#L229),
   [Apply:546-550](../../../web/components/chat/ConfirmationDirectEdit.tsx#L546-L550)).
   There is no consumer that takes a TVM input change and recomputes its answer
   immediately. Python must still own the arithmetic; duplicating it in the
   browser would split the numerical truth.
4. **Shared identity and ordering for recomputations.** The pending-card writer
   already has guarded source metadata and conversation activity, but its
   assembly/checkpoint synchronization is bound to confirmation state
   ([writer:341-390](../../../src/argus/api/chat/confirmation_lifecycle.py#L341-L390)).
   A live input editor needs the latest input revision to own the displayed
   answer, so an older response cannot replace a newer one. The shared loop
   must define whether the same card is updated, how inputs and answer persist
   together, and how a subsequent conversation finds it. The probe neither
   writes persistence nor invents a second lifecycle.

These are requirements inferred from inspected owners and the failed probes.
No route, editor, registry, recomputation mechanism or UI was built.

## 4. What must the registry declare that today's registry cannot express?

Today's registry derives strategy/indicator allow-lists from
`STRATEGY_CAPABILITIES` ([registry:20-67](../../../src/argus/domain/capability_registry.py#L20-L67)).
Its `ParameterSpec` has slot policy/default/allowed-values/copy, and an executable
`StrategyCapability` must name one of four backtest execution types
([schema:9-25,39-73](../../../src/argus/domain/strategy_capabilities.py#L9-L73)).
The probe verifies that `solve_for_unknown` fails both the registered-template
validator and the execution-type field ([probe:316-345](test_proof.py#L316-L345)).
An arbitrary `Any` value could hold metadata, but that would not give it an
owner, validation, execution or consumers.

| Needed declaration | Evidence and intended consumer |
| --- | --- |
| Tool identity, callable and typed return | The local declaration points to a real callable; the registry only enumerates strategy names/types. The tool returns the solved field's value, and the card identifies which field it solved ([declaration](declaration.py#L10-L20), [card](card.py#L4-L11)). The runtime needs to invoke it as a tool, potentially multiple times or alongside other tools, without classifying named questions. |
| Five typed optional arguments with exactly one unknown | “One blank across these five” is a cross-argument rule, not five independently required/defaultable slots. Zero must not trigger a fallback. The compute signature and validator own this today in the proof ([compute:11-39](compute.py#L11-L39)). Generate tool descriptions/schema from the eventual canonical declaration without a universal input model or per-scenario schema. |
| Domain, units and failure semantics | End-of-period payments, signed cash flows, effective rate per payment period, one currency, fractional-period meaning, unique-root restrictions and numerical search limits must travel with the tool. A bounded/invalid/ambiguous result must not masquerade as an answer ([compute:18-24,74-118](compute.py#L18-L118), [tests:73-104](test_proof.py#L73-L104)). The prototype's `ValueError` boundary still needs a shared typed outcome contract for production. |
| Cost, confirmation and progress policy | This tool is local, has zero external calls and answers first. Those facts must drive dispatch and progress, instead of the hardwired confirm/backtest stages. The local policy fields currently have no runtime reader ([declaration:14-19](declaration.py#L14-L19)). |
| Versioned result/card binding and input fact projection | The declaration must bind a result type to its card and typed inputs, so live delivery, reload and localized copy derive from the same facts. Open message metadata alone does not supply the missing classifier, hydration or renderer. Do not make the solver manufacture benchmark, return or date-range values. |
| Edit/recompute and lifecycle policy | Declare which known inputs can change and that those changes recompute while retaining the selected unknown. Shared machinery must own revisions, supersession, disclosure and continuity. The fixed `EditOperation.target` and confirmation writer cannot express this today; widening that model-facing vocabulary is not a shortcut authorized by this proof. |

The boundary correction should preserve the serializer-pinned state class
paths at [api/state.py:76-93](../../../src/argus/api/state.py#L76-L93). It should
make neutral contracts reachable without loading the catalog or planner,
then let the existing backtest behavior consume that shared machinery. Nothing
in this report authorizes moving those classes, widening `EditOperation.target`,
or modifying the interpreter.

## Reproduce and inspect

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 poetry run pytest docs/reports/lift-loop-lane-c/test_proof.py -o addopts='' -q
poetry run ruff check docs/reports/lift-loop-lane-c/*.py
```

Observed on Python **3.10.20**: **93 tests passed**; Ruff passed. The first
arithmetic run against the unimplemented solver failed 56 tests; the card
projection likewise failed before implementation. A separate regression
caught loss of a small positive growth factor through cancellation; its
[focused test](test_proof.py#L503-L504) now passes.

To refresh the checked-in raw observations, prefix the pytest command with
`LANE_C_EVIDENCE_PATH=docs/reports/lift-loop-lane-c/evidence.json`.
Ordinary reruns do not rewrite the evidence. Its source base identifies the
inspected production tree; its file hashes identify the working proof tested
before commit. Fresh-process output includes actual imported modules and
returned values, not only a pass/fail assertion.

The user-defined finishing bar applies: no eval, fingerprint regeneration,
browser QA, backtest-suite run, paid provider call, deploy or merge. Those are
not evidence claimed by this report. The interpreter fingerprint remains
byte-identical to the recorded base; no production file changed. This branch
is an inspection artifact and must remain a draft PR, never a release candidate.
