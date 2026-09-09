# Registry verification support

These are early working-tree observations for the registry lane, not a final
candidate scorecard or release claim. No provider calls were made. The original
`docs/reports/lift-loop-lane-c/evidence.json` remains unchanged.

## Lane C probe migration

Lane B commit `67323a5118dcee0b0f2b106a39756de2d8d50193` removed the private
`confirmation_lifecycle._stamped_card_metadata` helper and moved its behavior
to `domain.pending_artifacts.stamp_pending_artifact`. Lane C still imported
the removed name. Running its 31 subprocesses separately produced 22 returned
observations, six expected blocked imports, and three lifecycle import errors.
The shared pytest observation fixture turned those three stale commands into
32 setup errors, obscuring which probes were broken.

Only `probe_lifecycle` changed. It now calls the shared stamper with an explicit
test fixture describing the historical confirmation metadata layout. This does
not claim that the current production confirmation adapter is independent of
backtesting: its layout lives in `stages/artifact_context.py`, whose imports
still reach backtest bodies. The probe retains both original assertions: an
unselected calculation-card key is unchanged, and the selected confirmation
card receives its superseded state. The planner, display-fact, registry, and
lifecycle-writer negative assertions were not weakened.

- `lane-c-before.json` retains all 31 individually observed subprocess results,
  including the three original exceptions, source head, probe hash, and the
  historical evidence hash.
- `lane-c-after.json` retains the complete migrated matrix. **93 tests passed**,
  including all 31 subprocesses. All 28 unaffected return values and import
  outcomes match the before matrix. Its historical evidence hash still matches
  the untouched original file.

The recorded source head identifies the checkout parent, not an exact committed
registry implementation. Run the complete harness again at the final candidate
and retain a new observation file rather than overwriting either matrix here:

```sh
PYTHONDONTWRITEBYTECODE=1 \
LANE_C_EVIDENCE_PATH=docs/reports/evidence/registry/verification/lane-c-current.json \
poetry run pytest docs/reports/lift-loop-lane-c/test_proof.py -o addopts='' -q
```

## Generated model-facing contract

The old fingerprint saw selected Python string literals. Changes to a generated
catalog description, schema constraint, capability answer, or intent enumeration
could therefore leave the fingerprint unchanged. Seven new checks first failed
against that extractor; the existing static-checkout control passed.

The extractor now measures the emitted catalog schemas and capability text,
the exact response model returned by `interpretation_response_model`, and the
rendered interpreter system prompt. Their entries are
`generated/tool_catalog.json`, `generated/interpretation_response_schema.json`,
and `generated/interpreter_system_prompt.json` in the fingerprint. These names
identify generated measurements, not additional sources of product truth.

A fresh subprocess imports the requested checkout, with network operations
refused and provider credentials blanked. Four explicit profiles measure
research enabled/disabled crossed with execution realism enabled/disabled.
The subprocess clock is fixed to `2000-01-01` so a new calendar day does not
change the fingerprint. Profile metadata and the fixed date are recorded.
JSON object ordering is normalized; tool-list ordering and all schema facts
remain measured. Thirteen focused tests pass, including changed generated
facts, cross-checkout isolation, ambient environment isolation, generated
strategy capability changes, and an attempted network operation that fails
closed. Removing the generated factory removes its fingerprint entries and
therefore cannot silently retain an accepted current fingerprint; historical
checkouts that predate the factory remain readable for comparison.

```sh
PYTHONDONTWRITEBYTECODE=1 poetry run pytest \
  tests/test_interpreter_prompt_surface.py \
  tests/test_tool_checkpoint_serialization.py \
  tests/test_agent_runtime_checkpointer.py \
  tests/domain/test_tool_registry_import_boundary.py \
  tests/agent_runtime/test_shared_loop_import_boundary.py \
  -o addopts='' -q
```

The new declaration-import check first failed because the declaration module
did not yet exist; the neutral transport and pending-artifact owners passed.
After the declaration implementation appeared, the expanded command above
passed **40 tests** covering generated fingerprints, neutral-tool and shared-loop
imports, and existing/new checkpoint behavior. The
production `build_agent_runtime_checkpoint_serde()` serializes `RunState` and
`TaskSnapshot` containing repeated calls, successful and bounded outcomes, and
typed cards as msgpack. Reload preserves nested model types, call order, a known
zero, a blank value, and a bounded result without an answer. The serializer
allowlist in `api/state.py` was unchanged; no checkpoint class moved or renamed.

The committed prompt fingerprint and required live scorecard remain the release
captain's gate.

## Measurement harness contract migration

This subsection records the initial migration before paid measurement. Its
research-intent assumption and incomplete completion check are superseded by
the observation repair below. The original comparison artifact is preserved.

The old harness stopped at interpret/confirm/clarify. A fresh catalog response
requests dispatch before a backtest confirmation or research response exists,
so renaming intent expectations alone would have measured an incomplete path.
The harness now invokes the production registered execute owner for explicit
calls on initial and follow-up turns. Fresh backtests stop at the actual
confirmation handoff; no approval or execution is fabricated. Existing Run
button fixtures keep their validated-approval stopping point.

Raw `stage_outcomes`, named `execution_trace`, all selected call IDs and typed
arguments, execution records, and result cards remain in the scorecard.
`acceptance_stage_outcomes` preserves the old behavioral milestones by removing
only the interpreter's new scheduling edge when real registered execution has
returned. Its actual outcome remains checked. Missing dispatch cannot remove
an unexpected stage or count as an answer.

`measurement-contract-migration.json` compares the working fixtures with
integration `9e8b59b23f29d432ec7603c42f7362137b1ee21f`. All 68 IDs, prompts,
snapshots, actions, stage milestones, launch facts, delivery requirements, and
prose criteria are unchanged. Only intent names and the following justified
ownership changes differ:

- Nine discovery cases replace the old `asset_discovery` act requirement with
  successful declared dispatch and `calculate`. Their original relationship,
  anchors, category, asset class, and freshness checks read actual
  peer-expansion arguments. This operation is the declaration that carries
  those existing candidate-discovery facts; composed calls remain allowed.
- Current macro curiosity requires successful declared retrieval and
  `calculate`. The fixture does not prescribe a tool name or forbid composition.
- Historical labels normalize through the canonical state-model owner. Existing
  capability, unsupported-recovery, and delivery checks stay exact.

The initial eight new dispatcher checks failed against the old harness.
The final battery also covers zero calls, one call, two distinct calls, one
call twice, known zero, a real backtest confirmation, follow-up dispatch,
bounded/invalid/unavailable results, and independent discovery-fact mutations.
The delivery fault-injection factory supplies explicit synthetic execution
records so removing delivery remains the only mutation; it now covers all
68 cases. These authored records do not claim a provider run.

The expanded mocked command in `tests/evals/README.md` passed **269 tests**.
After the trace extraction, the combined mocked, fingerprint, checkpoint, and
import command passed **309 tests in 16.02 seconds**. Ruff also passed; the
measurement harness remains within its existing 1,250-line modularity limit.
All provider work was mocked or absent. The concrete retry trajectory initially
returned `confirmation_required` (409) on the worker while the unchanged test
passed against the verified detached integration source; the runtime owner
fixed that regression, and it is included in the green mocked run.

Before paid measurement, the announced estimate was revised to **$1.50–$3** for
one full 68-case pass, not a cap. Ten cases require research: four stable
discovery calls, five current-source discovery calls, and one current macro
lookup. Expect roughly ten declared research invocations and six current
retrievals when uncached, plus existing extraction/voicing. The old interpreter
already invoked those provider owners, so these are moved work rather than ten
net-new provider calls. PR #565 reported $1.11306 for the full suite and about
$0.11035 for those ten cases, with seventeen receipts lacking reported costs.
The larger generated prompt/schema and cache uncertainty justify the higher
estimate; actual receipts must settle spend. No paid run was performed here.

## Final implementation checks before paid measurement

The full backend run finished with 6,679 passed, 571 skipped and five failures.
Three were generated-schema test-client compatibility in issue 498; the focused
three passed after the client accepted the exact derived schema without changing
the compound-edit assertions. One was a stale OpenAPI description; all 24
OpenAPI/Alpha artifact checks passed after regeneration. The remaining failure
is the required measured fingerprint, deliberately still pointing at its prior
scorecard until the live run has completed. Skips include opt-in provider and
local database checks; the separate nine-case PostgreSQL proof is recorded in
`../persistence-proof.md`.

The full runtime/spine sweep passed 2,201 tests. Frontend unit tests passed 1,628
cases; all 14 fixture-browser cases passed, with the eight affected cases
revalidated after the final edit-liveness fix. Frontend lint passed with eight
existing warnings, and the production build passed after permitting its local
compiler port. Backend Ruff and the modularity budget passed. These are
implementation checks, not a terminal CI or release-readiness claim.

## Post-scorecard observation repair

The first registry scorecard remains in `../live-measurement-initial.json`,
measured at `3c4f5aab93f1928d999a20fc34c4b0a6bcecf5a8` under its original
harness and fixture hashes. It has not been regraded. Diagnosis found six
research failures caused only by the migrated intent expectation, plus two
research cases with an intent mismatch and a separate typed or prose failure.
Those separate failures remain failures to investigate.

The old harness observed research after its stage completed within interpret.
After registered dispatch moved that work into execute, the harness still read
only the initial interpreter patch. The actual research owner sets `follow_up`
after execution, regardless of whether the model initially selected `explain`,
`calculate`, or `follow_up`. The initial fixture migration had additionally
required `calculate` for all research. That was an unnecessary model
classification requirement, rather than an observation of executed work.

The corrected `intent` comes from applying actual stage patches in order;
`primary_intent` retains the interpreter's original value. The nine discovery
expectations return to the original canonical `follow_up`, and macro curiosity
returns to its original allowed canonical labels. Successful declared dispatch,
all original arguments, financial facts, recovery, clarification, approval,
delivery, and prose assertions remain. No question-to-tool mapping or new
intent policy was added.

Backtest execution now hands preparation to confirm before that owner can
request missing fields. The acceptance trace removes a readiness handoff only
when the actual next event is confirm requesting clarification. The same
adjacent handoff is normalized in expected milestones. Raw stage names and
outcomes remain unchanged; missing confirm or clarify events still fail, and
readiness leading to real approval is retained. This is a structural comparison
rule, not an exception for the Spanish DCA fixture.

An answer-required dispatch must also have a succeeded typed result card with
`presentation.answer` or a nonblank `presentation.narrative`, matching an
executed call's outcome. Private chat delivery accepts sourced narrative without
a numeric headline; public receipt eligibility intentionally remains narrower.
A successful queued
job without an answer cannot pass. One completed answer can accompany another
honestly pending call; the original delivery assertions still establish the
requested content. Queue-only contracts do not acquire an answer requirement.
The delivery mutation tests use authored matching records and cards to keep
their original offered-content checks isolated.

The execution evidence also preserves the existing research sidecar's reported
`cost_usd`, `latency_ms`, `invocations`, and `cache_status`, per call. The whitelist
excludes other private effects, keeps null and zero distinct, and does not
calculate prices, fees, or totals. This is capture of existing facts only.

The observation tests first produced **16 failures and five passing controls**;
all 21 passed after the repair. The additional usage-capture test first failed
on missing evidence and then passed. The focused dispatcher, observation, and
delivery command passed **123 tests**. The complete mocked command plus the
issue 498 compound-edit checks passed **294 tests in 8.40 seconds**. No provider
calls were made. `measurement-observation-repair.json` records the fixture
comparison and deterministic evidence. A new full live run must measure this
harness; these checks do not turn the initial scorecard into a passing run.

Review found two further harness gaps. Initial and follow-up dispatch omitted
the trusted snapshot and metadata that interpretation had already received.
Both paths now pass the same objects through; two actual-handler identity tests
failed before this handoff and passed after it. The unchanged follow-up metadata
builder moved into the existing dispatch helper to keep the main harness within
its budget. No new context is invented or recovered from prose.

The first completion predicate also incorrectly treated public receipt
eligibility as private chat delivery. An actual research presenter can deliver
a sourced narrative with no numeric headline. Its new regression failed while
three empty-narrative controls passed; the generic predicate now accepts that
nonblank narrative or a typed answer, still requiring the matching successful
call and outcome. Pending, blank, unrelated, and failed result controls remain.
After both corrections, all **28 observation tests** and the full mocked command
plus issue 498's original compound-edit checks passed: **300 tests in 9.05
seconds**. Ruff, diff checks, and the shared modularity gate passed; the main
harness is **1,240 lines against its existing 1,250-line limit**. No provider
calls were made.
