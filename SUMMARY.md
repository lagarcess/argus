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
| 2 | `interpreter/audits.py` | 14 classes | structured LLM audit-response schemas (import sink) | done |
| 3 | `interpreter/artifact_assumption_edit.py` | 6 fn | artifact assumption-edit application (brief named cluster) | done |
| 4 | `interpreter/asset_grounding.py` | 8 fn | asset-symbol normalization + grounding helpers | done |
| 5 | `interpreter/dca_audits.py` | 11 fn | DCA contract / family-continuity audit helpers | done |
| 6 | `interpreter/executable_grounding.py` | 6 fn | executable-strategy grounding audit | done |
| 7 | `interpreter/signal_rule.py` | 18 fn | signal-rule recovery / planning / grounding helpers | done |
| 8 | `interpreter/focused_extraction.py` | 7 fn | focused-strategy extraction messages / merge | done |
| 9 | `interpreter/strategy_builder.py` | 35 fn | `_strategy_from_llm`, slot cleaning, capital grounding, indicator defaults | done |
| 10 | `interpreter/draft_shape.py` | 18 fn | LLM strategy-draft shape predicates / underfill checks | done |
| 11 | `interpreter/run_field_audits.py` | 36 fn | stated-run-field fidelity, capability-conflict, latest-result routing helpers | done |
| 12 | `interpreter/capability_context_audits.py` | 4 fn | capability/context Q&A audit helpers | done |
| 13 | `interpreter/pending_option.py` | 10 fn | pending-response-option selection | done |
| 14 | `interpreter/readiness_helpers.py` | 3 fn | asset-universe-operation + readiness logging | done |
| 15 | `interpreter/starting_capital.py` | 6 fn | starting-capital audit helpers | done |
| 16 | `interpreter/strategy_repair_predicates.py` | 7 fn | strategy-repair predicates, vague-start, execution anchors | done |
| 17 | `interpreter/temporal_repair.py` | 11 fn | temporal/date-window repair + focused-date extraction | done |

The pinned core (87 fn / ~4,121 LOC, incl. `OpenRouterStructuredInterpreter`) and
`_selected_thread_metadata_context` (17 LOC, not worth a module) stay in the facade.

### Gating cadence
Per-commit gate is `pytest tests/agent_runtime/ -n 12` via `pytest-xdist` (installed
into the local venv only — **not** added to `pyproject`/`poetry.lock`; invisible to the
deliverable). Validated to reproduce the exact baseline (11 failed / 795 passed) in ~85s
vs ~210s serial. A final serial full-`tests/` gate is run before handoff.

## Module map — `stages/interpret.py`

New package: `src/argus/agent_runtime/stages/interpret_internal/`. Same facade + re-export
discipline. The monkeypatch surface for `interpret` patches **imported names** (incl.
**string-form** `monkeypatch.setattr("…stages.interpret.invoke_openrouter_chat_completion", …)`
17×, `resolve_asset`, `date`, `fetch_alpaca_market_movers_packet`, …) but **no private
functions**. Pinned (under the full patched set): 48 fn / ~2,728 LOC (the public
`interpret_stage*`, the `_stage_result_from_interpretation` orchestrator, every
LLM-invoking compose function). Movable: 115 fn / ~2,290 LOC.

| # | Module | Members | Concern | Status |
|---|--------|---------|---------|--------|
| 1 | `interpret_internal/shared.py` | 4 fn | cross-cutting leaf helpers (import sink) | done |
| 2 | `interpret_internal/answer_composition.py` | 21 fn + 1 cls + 2 const | non-LLM answer-composition support (packet grounding, fact packets) | done |
| 3 | `interpret_internal/asset_resolution.py` | 59 fn + 1 cls + 3 const | asset resolution / canonicalization / requested-asset / artifact-target / indicator-simplification | done |
| 4 | `interpret_internal/date_contract.py` | 6 fn + 1 const | current-message date/run-field contract | done |
| 5 | `interpret_internal/contextual_merge.py` | 19 fn + 1 const | strategy contextual-merge across turns | done |
| 6 | `interpret_internal/offline_recovery.py` | 6 fn + 1 const | interpreter-unavailable / offline recovery results | done |
| 7 | `interpret_internal/route_repair.py` | 2 fn | pending-need route repair | done |

---

## Results (handoff state)

| File | Before | After | Reduction | Modules |
|------|-------:|------:|----------:|--------:|
| `llm_interpreter.py` | 10,467 | 5,279 | −50% | 18 |
| `stages/interpret.py` | 5,621 | 3,159 | −44% | 7 |

- **Tests:** `tests/agent_runtime/` green vs baseline (11 pre-existing failures unchanged,
  795 passing) — re-confirmed serially after the full llm_interpreter and interpret work.
- **Full `tests/` final gate:** `14 failed / 1593 passed / 1 skipped`. The 14 = the 11
  documented `agent_runtime` failures + 3 outside `agent_runtime`
  (`test_phase6_api_structure.py::test_api_main_is_only_app_entrypoint`,
  `test_openrouter_policy.py::test_requested_asset_answer_uses_semantic_candidate_audit_before_provider_validation` ×2).
  **All 3 were verified to fail identically on baseline `805b8d4`** → pre-existing, not
  regressions. No new failures anywhere.
- **mypy:** 14 errors (= baseline), relocated across the new modules; no new errors.
- **ruff:** clean across `src/argus/agent_runtime/`.
- **27 behavior-preserving commits**, not squashed; left **unpushed** for review.

## Process notes / lessons (for the reviewer)

1. **Monkeypatch pinning is the governing constraint.** Tests patch module-level names on
   `interpreter_module` / `interpret_module`. A call site that moves resolves the name in its
   new module namespace, so the patch silently misses → behavior change. Every call site of a
   patched name therefore stays in the facade. This (not cohesion) sets the floor on facade size.
2. **String-form patches matter.** `interpret` is also patched via
   `monkeypatch.setattr("dotted.path.name", …)`, which an AST scan for `setattr(obj, "name", …)`
   misses. Omitting `invoke_openrouter_chat_completion` first produced a real 28-failure
   regression; adding the string-form targets to the pinned set fixed it. (`llm_interpreter`
   has **no** string-form patches — verified.)
3. **Facade import surface is part of behavior.** Tests access `module.<ImportedType>` (e.g.
   `llm_interpreter.LLMDateRangeIntent`, 93×). `ruff --fix` removing a now-unused facade import
   silently drops that attribute. Fixed with a file-level `# ruff: noqa: F401` on both facades.
4. **Decorated symbols** (`@dataclass`) must be removed from the decorator line, not the
   `class`/`def` line, or an orphaned decorator is left behind.
5. **Gating:** `pytest-xdist` (`-n 12`, local-venv only) reproduces the baseline ~3× faster but
   can spuriously fail timeout-sensitive tests under load; any failure beyond the baseline 11 is
   re-verified serially before it counts as a regression. A final serial gate confirms.

## Blocked / deferred (with reason)

- **Neither facade reaches < ~1,500 lines**, because the test monkeypatch surface pins
  ~4,121 LOC (llm_interpreter) / ~2,728 LOC (interpret) of call sites to the facade.
  Forcing it below would require changing the tests' patch seams — a behavior-adjacent,
  out-of-scope change. Documented per the brief's stop-and-document rule; not forced.
- The pre-existing 11 test failures and 14 mypy errors are **untouched** (out of scope).
