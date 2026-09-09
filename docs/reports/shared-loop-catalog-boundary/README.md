# Shared loop catalog boundary

## Scope and integration base

Founder-dispatched first half of the registry item. Lane C report/probes read
from PR #566, head `f8cff8302a51d80a7539690a1be9be1cd9655fd9`.
Original and fetched integration base: `76f5947b6ba90d0040e2fe94d68ec2c51750379a`.
Reconciled before inspection; the detached checkout was already at this base.

No state class moves or renames, checkpoint serializer edits, interpreter edits,
model-facing text/schema changes, live evaluations, or prototype promotion.

## Full edge inventory, recorded before implementation

A runtime import tracer records imports even when the target is already cached,
so a first successful load cannot hide another path. The entry modules were
`state.models`, `api.schemas`, `next_experiments_contract`, and
`artifacts.lifecycle`. Normal Python package initialization is part of the trace.
All catalog-reaching edges in that closure follow (fully qualified module names):

| Importer | Imported module |
| --- | --- |
| `argus.agent_runtime` | `argus.agent_runtime.capabilities.contract` |
| `argus.agent_runtime` | `argus.agent_runtime.profile.response_profile` |
| `argus.agent_runtime` | `argus.agent_runtime.state.models` |
| `argus.agent_runtime.artifacts` | `argus.agent_runtime.artifacts.continuity` |
| `argus.agent_runtime.artifacts` | `argus.agent_runtime.artifacts.drafts` |
| `argus.agent_runtime.artifacts` | `argus.agent_runtime.artifacts.strategy_edits` |
| `argus.agent_runtime.artifacts.continuity` | `argus.agent_runtime.artifacts.drafts` |
| `argus.agent_runtime.artifacts.continuity` | `argus.agent_runtime.artifacts.strategy_edits` |
| `argus.agent_runtime.artifacts.continuity` | `argus.agent_runtime.state.models` |
| `argus.agent_runtime.artifacts.drafts` | `argus.agent_runtime.state.models` |
| `argus.agent_runtime.artifacts.strategy_edits` | `argus.agent_runtime.state.models` |
| `argus.agent_runtime.capabilities` | `argus.agent_runtime.capabilities.contract` |
| `argus.agent_runtime.capabilities.contract` | `argus.agent_runtime.state.models` |
| `argus.agent_runtime.profile` | `argus.agent_runtime.profile.response_profile` |
| `argus.agent_runtime.profile` | `argus.agent_runtime.state.models` |
| `argus.agent_runtime.profile.response_profile` | `argus.agent_runtime.state.models` |
| `argus.agent_runtime.state` | `argus.agent_runtime.state.models` |
| `argus.agent_runtime.state.models` | `argus.domain.capability_registry` |
| `argus.api.schemas` | `argus.domain.capability_registry` |
| `argus.domain.capability_registry` | `argus.domain.strategy_capabilities` |

Every `agent_runtime.*` entry first initializes `argus.agent_runtime`, including
`next_experiments_contract` and `artifacts.lifecycle`; the latter additionally
initializes `artifacts`. These implicit parent edges are included in the scope.

The two independent direct consumers are `state.models` (registered template
annotation) and `api.schemas` (executable template validation and eagerly built
OpenAPI enum). Both reach `capability_registry`, which eagerly imports
`strategy_capabilities` and computes four derived sets. Merely moving the API
validator import would leave its schema enum as an import-time catalog read.
The legacy `Strategy._tolerate_retired_template` reader also uses the executable
set; its existing behavior is retained through a function-local registry import.
It runs only for a supplied Strategy template, never for a general Message.

The API reader path was also traversed: `schemas -> artifact_presentation ->
artifact_presentation_kind / result_figures -> benchmark_comparison /
display_figure`. `schemas` also reads `conversation_preview_contract`,
`decision_contract`, and `feedback_context`. None reaches the catalog at this
base. No alternate catalog edge was found in the general entry closure.

Repository-wide direct catalog/registry imports outside this closure:

| Consumer | Catalog responsibility retained |
| --- | --- |
| `domain.slot_normalizer` | Strategy parameter normalization |
| `domain.backtesting.config` | Engine template validation |
| `domain.backtesting.charts` | Strategy-specific chart policy |
| `agent_runtime.run_field_contract` | Strategy/indicator field facts |
| `agent_runtime.strategy_contract` | Backtest admission |
| `agent_runtime.capabilities.answers` | Indicator/template reachability answers |
| `agent_runtime.artifact_edit_planner` | Strategy edit interpretation/application |
| `agent_runtime.llm_interpreter_types` | Model-facing strategy vocabulary |
| `agent_runtime.interpreter.unsupported_admission` | Strategy admission audit |
| `agent_runtime.interpreter.run_field_audits` | Strategy-field audit |
| `agent_runtime.interpreter.pending_option` | Strategy pending choices |
| `agent_runtime.interpreter.shared` | Interpreter strategy helpers |

Those are backtest consumers, not general containers, and remain catalog-bound.
Lane C's planner, display-fact projector and lifecycle writer remain blocked by
the body guard. This lane makes the existing open envelopes reachable; it does
not make these backtest bodies into a general calculation loop.

## Repair plan

1. Keep the catalog and derived sets at their existing owner.
2. Give registered/executable template annotations one lightweight contract
   owner. Validation and JSON-schema enum generation resolve the existing
   derived sets only when requested; annotation construction does neither.
3. Keep public template imports compatible through re-exports. General models
   use the lightweight contract; all pinned state classes stay where they are.
4. Run Lane C's 31 probes with the four newly reachable catalog-guard outcomes
   expected to return; retain the other body/shape failures as boundaries.
   Add a normal-CI fresh-process guard derived from Lane C for the general entry
   modules and actual envelope JSON round trips.
5. Compare all API, state and interpreter-type JSON schemas against the base,
   verify the committed interpreter fingerprint, and run existing backtest and
   focused/mocked suites unchanged. Finish with exact-head CI and Codex review.

## Implementation and local verification

Registered and executable annotations now live in
`domain.strategy_template_contract`. One constraint implementation owns both
validation and schema publication, with callbacks to the existing canonical
registry sets. It does not copy the catalog or add another template list/cache.
`capability_registry.RegisteredStrategyTemplate` and `api.schemas.StrategyTemplate`
remain compatible aliases. Catalog access still occurs for a strategy-bearing
validation or when publishing a schema that includes a strategy enum.

The independent Codex diff review returned **no actionable findings**. It checked
all registered templates, executable/draft rejection, JSON round trips, legacy
Strategy fallback and public alias identity. This is the local review record;
the terminal exact-head GitHub review/CI audit belongs on the PR after both finish.

Integration advanced during verification to
`3738fbec0bd4f96c0248abc52e6b2e2287a8c69c`. Reconciliation was a fast-forward, with no merge
commit. The intervening changes add Lane C documentation and mark it landed on
the roadmap. There is no shared runtime owner, API/data contract, UI state owner,
migration, environment variable or affected production test overlap. Acceptance
remains valid. The existing Lane C test expectation is now updated only for the
four successful catalog probes, leaving the solver and all probe bodies intact.

Observed locally on Python 3.10.20:

- Before the repair, the normal-CI import guard failed **15** cases on the catalog;
  two already-clean entry modules passed. After: **17 passed**.
- Lane C: **93 passed**, including all **31 fresh-process probes**. Transport,
  confirmation/facts envelopes, next-row contracts and retry lifecycle now pass
  the catalog guard. All formerly returned payloads are unchanged. Planner,
  display-fact and lifecycle-write bodies remain blocked as expected.
- Existing backtest/domain/runtime/API-import tests plus the mocked eval harness:
  **962 passed, 9 skipped**. The skips are existing Postgres integration tests
  gated by `ARGUS_TEST_POSTGRES_DSN`. No existing backtest test was edited.
- Legacy Strategy API read: **1 passed**, 95 unrelated tests deselected.
- All API, state and interpreter-type JSON schemas compared byte-for-byte with
  the original base: identical. The interpreter fingerprint checks passed; the
  committed fingerprint and all forbidden interpreter/serializer files are untouched.
- Repository Ruff, patch whitespace checks and the modularity budget passed
  after reconciliation, on the would-be merged tree.

[Raw observations](evidence.json) retain both complete Lane C probe matrices,
loaded-module lists, before/after import traces and hashes of the tested runtime
files. These are working-tree observations, explicitly identified as such;
exact-head revalidation and terminal CI/review links are recorded in the PR audit.
No live evaluation or browser/provider call is part of this lane.

## Reproduce

Run the current Lane C harness and the promoted CI boundary guard:

```sh
PYTHONDONTWRITEBYTECODE=1 poetry run pytest docs/reports/lift-loop-lane-c/test_proof.py -o addopts='' -q
PYTHONDONTWRITEBYTECODE=1 poetry run pytest tests/agent_runtime/test_shared_loop_import_boundary.py tests/domain/test_capability_registry.py tests/agent_runtime/test_state_models.py tests/test_interpreter_prompt_freeze.py -o addopts='' -q
```

The full regression selection also includes `tests/domain`, `tests/test_backtest*.py`,
`tests/test_chat_backtest_state_machine.py`, `tests/test_engine_signals.py`,
`tests/test_strategy_capabilities.py`, `tests/test_strategy_registry_i18n.py`,
`tests/agent_runtime/test_strategy_contract.py`,
`tests/agent_runtime/test_real_backtest_tool.py`, `tests/test_api_import_boundary.py`,
and the ten files in `tests/evals/README.md`'s Mocked Run command.
