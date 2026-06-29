# Spine Modularization — SUMMARY

Issue #131 — behavior-preserving structural refactor of the two agent-runtime
spine mega-files into cohesive modules. **Structure only; no logic/behavior change.**
Branch: `codex/spine-modularization`. Left **unpushed** for maintainer review/merge.

Scope = exactly two files:
- `src/argus/agent_runtime/llm_interpreter.py` (10,467 lines at baseline)
- `src/argus/agent_runtime/stages/interpret.py` (5,621 lines at baseline)

---

## Phase 0 — Baseline (re-measured on `805b8d4`, HEAD of branch)

The floor is **NOT green**. The gate is **"no NEW failures/errors beyond this
baseline,"** never "all green." Treated as the floor; **not fixed** (out of scope).

### Tests — `poetry run pytest tests/agent_runtime/ --no-cov -q -rf`
**`11 failed / 795 passed`** (209s). The 11 pre-existing failures (the floor):

1. `test_conversational_contract_hardening.py::test_unresolved_llm_benchmark_is_not_preserved_without_user_request`
2. `test_conversational_contract_hardening.py::test_provider_valid_llm_benchmark_is_not_preserved_without_user_request[TSLA…-TSLA-AN]`
3. `test_conversational_contract_hardening.py::test_provider_valid_llm_benchmark_is_not_preserved_without_user_request[AAPL…-AAPL-ON]`
4. `test_conversational_contract_hardening.py::test_stated_run_fidelity_audit_skips_complete_aligned_comparison`
5. `test_conversational_contract_hardening.py::test_current_year_so_far_refusal_enters_strategy_repair`
6. `test_conversational_contract_hardening.py::test_stated_run_fidelity_audit_skips_aligned_focused_repair`
7. `test_conversational_contract_hardening.py::test_stated_run_fidelity_audit_skips_aligned_focused_repair_capital`
8. `test_llm_interpreter_artifact_capability_repairs.py::test_llm_interpreter_audits_pending_asset_answer_despite_educational_copy`
9. `test_llm_interpreter_artifact_capability_repairs.py::test_supported_date_gap_escalates_before_unrelated_audits`
10. `test_llm_interpreter_semantic_contracts.py::test_failed_capital_recheck_uses_focused_strategy_repair_before_baseline`
11. `test_llm_interpreter_semantic_contracts.py::test_focused_strategy_repair_recovers_omitted_provider_assets`

### mypy — `poetry run mypy <the two files>`
**`14` errors** (the floor). 4 in `llm_interpreter.py`, 10 in `stages/interpret.py`.
Existing errors may **relocate** into new modules as code moves — that is allowed.

- `llm_interpreter.py`: L601 (`wait_for` arg-type), L664 (`wait_for` arg-type),
  L1112 (`StructuredInterpretation` artifact_target arg-type), L10215 (`float` arg-type).
- `stages/interpret.py`: L418, L419 (`no-any-return`), L2976 (assignment), L2977,
  L2981 (`attr-defined`), L2982 (`call-overload`), L2985 (`append` arg-type),
  L4649, L4792, L4864 (`_dedupe_resolution_provenance` list-invariance arg-type).

### ruff — `poetry run ruff check`
**Clean** (0 errors). Keep clean.

### Coverage (the two targets) — combined **86%**
- `llm_interpreter.py`: **84%** (589/3770 lines missing)
- `stages/interpret.py`: **89%** (242/2107 lines missing)

Coverage is high; the 795 passing tests characterize the vast majority of moved
code. Characterization tests are added only for a thinly-covered function that is
about to MOVE (the sole allowed test addition); none required so far.

---

## Key structural findings (drive the safe plan)

Deterministic analysis (AST) of both files established:

1. **Both internal call graphs are pure DAGs** — zero mutually-recursive function
   cycles. A provably-safe topological (leaf-first) extraction order exists.
2. **Purely declarative modules** — no `global` state, no import-time side effects,
   no `__all__`, no decorators on the moved standalone functions. Ideal for relocation.
3. **The public entry `OpenRouterStructuredInterpreter` is referenced only at its own
   definition** — no standalone function calls back into the class. The class stays in
   `llm_interpreter.py` as the facade; functions move out cleanly beneath it.

### ⚠️ Hard constraint: test monkeypatching pins ~40% of `llm_interpreter.py`

Tests do `monkeypatch.setattr(interpreter_module, "<name>", fake)` **670 times**.
This sets an attribute on the `llm_interpreter` module object. A call site only sees
the patch if it resolves `<name>` in the `llm_interpreter` namespace. **If a function
that calls a patched name is moved to another module, it resolves the name in its own
module namespace and the patch silently misses → behavior changes.** Therefore:

> **Every call site of a monkeypatched name must stay in the facade.**

Patched names include imported symbols (`invoke_openrouter_json_schema` 270×,
`resolve_asset` 218×, `openrouter_structured_model_candidates` 54×, …) and private
functions (`_request_current_turn_has_material_execution_evidence` 38×,
`_audit_stated_run_field_fidelity` 18×, `_repair_incomplete_strategy_extraction` 18×, …).

Computing the fixpoint (a function is **pinned** if it references a patched name, or
calls a pinned function — which would otherwise force a facade import cycle):

- **Pinned to facade: 87 functions / ~4,121 LOC** (the LLM-invoking core, the
  `_response_ready_for_runtime` orchestrator, the patched audits + their callers).
- **Safely movable: 207 functions / ~4,636 LOC.**

**Consequence:** the brief's "aim < ~1,500 lines" is **not achievable for
`llm_interpreter.py` without breaking behavior** — ~4,100 LOC is legitimately pinned
by the test monkeypatch surface. Per the brief ("if an extraction can't be done
without a behavior change, STOP and document"), the honest, behavior-preserving target
is **10,467 → ~5,800 LOC** (extract the 4,636 movable LOC + ~200 of relocated
constants/blank lines). If the maintainer wants a smaller facade, the prerequisite is a
separate (behavior-changing, out-of-scope) refactor of the test monkeypatch surface to
patch dependency seams instead of module globals.

---

## Module map — `llm_interpreter.py` (extraction plan, topological order)

New package: `src/argus/agent_runtime/interpreter/`. Each module receives a cohesive,
acyclic group of **movable** functions; `llm_interpreter.py` re-exports every moved
symbol (`# noqa: F401`) so the 296 external import references keep working unchanged.
The pinned core + `OpenRouterStructuredInterpreter` class stay in `llm_interpreter.py`.

Extraction order (deps-first; each module imports only `shared`/`audits` + earlier
concern modules — verified acyclic by AST graph analysis):

| # | Module | Members | Concern | Status |
|---|--------|---------|---------|--------|
| 1 | `interpreter/shared.py` | 20 fn + 5 const | cross-cutting leaf helpers + constants (import sink) | **done** |
| 2 | `interpreter/audits.py` | 14 classes | structured LLM audit-response schemas (import sink) | planned |
| 3 | `interpreter/artifact_assumption_edit.py` | 6 fn | artifact assumption-edit application (brief named cluster) | planned |
| 4 | `interpreter/asset_grounding.py` | 8 fn | asset-symbol normalization + grounding helpers | planned |
| 5 | `interpreter/dca_audits.py` | 11 fn | DCA contract / family-continuity audit helpers | planned |
| 6 | `interpreter/executable_grounding.py` | 6 fn | executable-strategy grounding audit | planned |
| 7 | `interpreter/signal_rule.py` | 18 fn | signal-rule recovery / planning / grounding helpers | planned |
| 8 | `interpreter/focused_extraction.py` | 7 fn | focused-strategy extraction messages / merge | planned |
| 9 | `interpreter/strategy_builder.py` | 35 fn | `_strategy_from_llm`, slot cleaning, capital grounding, indicator defaults | planned |
| 10 | `interpreter/draft_shape.py` | 18 fn | LLM strategy-draft shape predicates / underfill checks | planned |
| 11 | `interpreter/run_field_audits.py` | 36 fn | stated-run-field fidelity, capability-conflict, latest-result routing helpers | planned |
| 12 | `interpreter/capability_context_audits.py` | 4 fn | capability/context Q&A audit helpers | planned |
| 13 | `interpreter/pending_option.py` | 10 fn | pending-response-option selection | planned |
| 14 | `interpreter/readiness_helpers.py` | 3 fn | asset-universe-operation + readiness logging | planned |
| 15 | `interpreter/starting_capital.py` | 6 fn | starting-capital audit helpers | planned |
| 16 | `interpreter/strategy_repair_predicates.py` | 7 fn | strategy-repair predicates, vague-start, execution anchors | planned |
| 17 | `interpreter/temporal_repair.py` | 11 fn | temporal/date-window repair + focused-date extraction | planned |

The pinned core (87 fn / ~4,121 LOC, incl. `OpenRouterStructuredInterpreter`) and
`_selected_thread_metadata_context` (17 LOC, not worth a module) stay in the facade.

### Gating cadence
Per-commit gate is `pytest tests/agent_runtime/ -n 12` via `pytest-xdist` (installed
into the local venv only — **not** added to `pyproject`/`poetry.lock`; invisible to the
deliverable). Validated to reproduce the exact baseline (11 failed / 795 passed) in ~85s
vs ~210s serial. A final serial full-`tests/` gate is run before handoff.

`stages/interpret.py`: analyzed separately (335 monkeypatches, dominated by
`resolve_asset` 304×); module map TBD — see Phase 0 findings carry over.

---

## Per-commit log

1. `interpreter/shared.py` — 20 cross-cutting leaf helpers + 5 shared constants
   (foundation import sink). Gate: 11 failed / 795 passed (baseline); mypy 14; ruff clean.
2. `interpreter/audits.py` — 14 structured LLM audit-response Pydantic schemas
   (import sink for audit modules + facade). Gate: baseline (an xdist-only extra failure
   confirmed passing serially — load-sensitive timeout flake, not a regression); ruff clean.

> Note: `pytest-xdist` can spuriously fail a timeout-sensitive test under parallel load.
> Protocol: any failure beyond the baseline 11 is re-checked serially; only a serial
> failure counts as a regression.

## Blocked / deferred (with reason)

- **`llm_interpreter.py` cannot reach < ~1,500 lines** without breaking the test
  monkeypatch surface (see "Hard constraint" above). Documented, not forced.
