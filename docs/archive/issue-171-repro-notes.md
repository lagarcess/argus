# Argus issue #171 repro scout notes

Base checked: `eca0b7e` (`origin/codex/private-alpha-next`).

Scope kept read-only for runtime code. Only `tests/agent_runtime/test_llm_interpreter_semantic_contracts.py`
and this notes file were changed.

## Baseline mocked suite at HEAD

Command:

```bash
poetry run pytest --no-cov tests/agent_runtime tests/evals/test_measurement_eval_harness.py -q -rf
```

Result at `eca0b7e`: `20 failed, 944 passed, 4 xfailed`.

Pre-existing failures observed before adding #171 gates:

- `tests/agent_runtime/test_conversation_stages.py::test_clarify_offline_fallback_uses_product_language`
- `tests/agent_runtime/test_conversation_stages.py::test_clarify_spanish_unsupported_recovery_fallback_uses_structured_options`
- `tests/agent_runtime/test_interpret_stage.py::test_spanish_atr_underfilled_draft_routes_to_unsupported_recovery`
- `tests/agent_runtime/test_interpret_stage.py::test_spanish_atr_llm_indicator_metadata_routes_to_unsupported_recovery`
- `tests/agent_runtime/test_interpret_stage.py::test_supported_strategy_label_with_explicit_unsupported_indicator_needs_recovery`
- `tests/agent_runtime/test_interpret_stage.py::test_executable_artifact_patch_does_not_require_strategy_thesis`
- `tests/agent_runtime/test_interpret_stage.py::test_supported_indicator_capability_composer_failure_uses_locale_recovery`
- `tests/agent_runtime/test_interpret_stage.py::test_supported_indicator_capability_contradiction_uses_locale_recovery`
- `tests/agent_runtime/test_interpret_stage.py::test_market_movers_without_packet_uses_user_language`
- `tests/agent_runtime/test_interpret_stage.py::test_active_confirmation_cost_refinement_uses_artifact_planner`
- `tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py::test_vague_valuation_prompt_with_short_copy_gets_structured_recovery`
- `tests/agent_runtime/test_llm_interpreter_grounding_and_signal_rules.py::test_llm_interpreter_plans_active_artifact_asset_append_after_model_failure`
- `tests/agent_runtime/test_llm_interpreter_grounding_and_signal_rules.py::test_llm_interpreter_plans_active_artifact_asset_operation_when_model_keeps_benchmark`
- `tests/agent_runtime/test_llm_interpreter_grounding_and_signal_rules.py::test_pending_signal_rule_answer_uses_entry_rule_metadata`
- `tests/agent_runtime/test_llm_interpreter_semantic_contracts.py::test_pending_response_option_selection_wins_over_generic_asset_parse`
- `tests/agent_runtime/test_llm_interpreter_semantic_contracts.py::test_pending_response_option_selection_handles_approval_like_answer`
- `tests/agent_runtime/test_refine_action_edit_routing.py::test_refine_execution_cost_edit_preserves_pending_run_fields`
- `tests/agent_runtime/test_spanish_runtime_transcripts.py::test_spanish_approval_routes_by_llm_semantics_not_text_matching`
- `tests/agent_runtime/test_workflow.py::test_workflow_confirmation_assumption_action_stays_in_clarification`
- `tests/agent_runtime/test_workflow.py::test_workflow_spanish_adjust_assumptions_answer_reenters_interpreter`

Do not attribute those 20 to the new #171 tests.

## New Phase-1 gates

Both gates are strict xfails in `tests/agent_runtime/test_llm_interpreter_semantic_contracts.py`.

Sig1 gate:

- Test: `test_unsupported_recovery_calendar_year_intent_survives_without_bare_year_provenance`
- Covers: the mocked runtime-readiness recovery path for a recovery/unsupported draft with provider-backed `AAPL`, default `SPY`, and `date_range_intent(kind="calendar_year", year=2024)` must keep `date_range == {"start": "2024-01-01", "end": "2024-12-31"}`.
- Current `--runxfail` failure: the typed observation is `{"assets": ["AAPL"], "date_range": None}`.
- Root check: `a5ac38b^` (`a80d681`) already fails this deterministic mocked shape, so the mocked gate does not confirm `a5ac38b` as the first bad commit. The first relevant boundary seen for the mocked unsupported-recovery shape is the #165 unsupported-request/runtime-context path around `a80d681`; before that boundary the same asset-context recovery shape is not fully present.

Sig2 gate:

- Test: `test_company_name_basket_context_survives_underfilled_repair_to_confirmation`
- Covers: provider-backed Target/Walmart/Costco company-name context must survive an underfilled supported-draft repair path to a typed executable buy-and-hold confirmation.
- Asserts typed outcomes only: `asset_universe == ["TGT", "WMT", "COST"]`, `date_range == {"start": "2024-01-01", "end": "2024-12-31"}`, `capability_verdict == "executable"`, `stage_outcomes == ["ready_for_confirmation", "await_approval"]`.
- Current `--runxfail` failure: provider-backed assets and date survive, but the repaired turn remains clarification-shaped, so the derived verdict is `unsupported` and `stage_outcomes == ["needs_clarification"]`.
- Root check: consistent with the #165/#150 integration-health cluster around `a80d681`, especially the underfilled repair/runtime-context path. This gate captures the full Target/Walmart/Costco executable basket path that the existing #150 xfails do not cover.

## #150 strict xfail coverage

Confirmed existing #150 strict xfails:

```bash
poetry run pytest --no-cov \
  tests/agent_runtime/test_conversational_contract_hardening.py::test_dca_cadence_terms_are_not_promoted_to_assets \
  tests/agent_runtime/test_conversational_contract_hardening.py::test_interpret_stage_repairs_missing_asset_when_benchmark_owner_is_known \
  tests/agent_runtime/test_conversational_contract_hardening.py::test_pending_buy_hold_simplification_clears_stale_indicator_rule \
  -q -rf
```

Result: `4 xfailed`.

Those cover cadence-token promotion, missing-asset repair with known benchmark ownership, and stale pending simplification state. They do not cover the full Target/Walmart/Costco executable basket path, so Sig2 adds that missing mocked gate.

## Verification

Mocked suite after adding the two gates:

```bash
poetry run pytest --no-cov tests/agent_runtime tests/evals/test_measurement_eval_harness.py -q -rf
```

Result: `20 failed, 944 passed, 6 xfailed`. The 20 failures are the same pre-existing baseline failures listed above; the xfail count increased by the two #171 gates.

Focused gate checks:

```bash
poetry run pytest --no-cov \
  tests/agent_runtime/test_llm_interpreter_semantic_contracts.py::test_unsupported_recovery_calendar_year_intent_survives_without_bare_year_provenance \
  tests/agent_runtime/test_llm_interpreter_semantic_contracts.py::test_company_name_basket_context_survives_underfilled_repair_to_confirmation \
  -q -rf
```

Result: `2 xfailed`.

Failure proof:

```bash
poetry run pytest --no-cov --runxfail \
  tests/agent_runtime/test_llm_interpreter_semantic_contracts.py::test_unsupported_recovery_calendar_year_intent_survives_without_bare_year_provenance \
  tests/agent_runtime/test_llm_interpreter_semantic_contracts.py::test_company_name_basket_context_survives_underfilled_repair_to_confirmation \
  -q -rf
```

Result: `2 failed`, with the typed failures described above.

Lint:

```bash
poetry run ruff check tests/agent_runtime/test_llm_interpreter_semantic_contracts.py
```

Result: passed.
