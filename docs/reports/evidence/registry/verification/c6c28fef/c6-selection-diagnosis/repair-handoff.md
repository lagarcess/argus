# Eval-only observer repair handoff

Owned files: `tests/evals/measurement_selection.py` and `tests/evals/test_measurement_selection.py`. No runtime owner, fixture expectation, rubric, fingerprint, provider setting, historical result, Git index, or commit changed. Parent-authorized peer projection is included with the original semantic-context task.

## Changes

- `selection_judge_context` explicitly selects delivered identities, reasons, figures, dates, citations, citation origin, retrieval timestamp, and semantic source-period bounds. Internal cache data class, retention TTL, and query-kind taxonomy no longer appear in its model-facing facts. The complete original `evidence_policy` stays in `typed_outcome.asset_discovery` for scorecard serialization and deterministic currentness checks. Those checks and the existing relevance rubric are AST-identical to frozen c6c28fef.
- `observe_selection` reads typed peer identities from the same bound research effect that already supplies subjects. Each peer must still occur in the validated declared result's subject/peer identity set. No name is inferred from input text or action labels. Missing result membership, mismatched effect artifact, and missing peer class remain unproven.

## Free TDD and verification

- `semantic-red.log`: 2 new serialized-payload tests failed on leaked `evidence_policy`; 3 source-period/max-age controls passed.
- `semantic-green.log`: all 5 passed after the intentional projection.
- `peer-red.log`: the valid subject+peer delivery failed with the same unproven-action error as the recorded IPO case; all 3 invalid-binding/class controls passed.
- `selection-green.log`: 42 focused tests passed, including all new and existing mutation controls.
- `mocked-gate-final.log`: the exact 14-file Mocked Run command from `tests/evals/README.md`, using .venv Python 3.10 with `--no-cov`, passed 378 tests. Provider calls were mocked; this is not live acceptance evidence.
- Ruff check/format and changed-file whitespace checks passed. `modularity.log` reports no violations. `observer-repair.diff` preserves the owned-file delta.

## Final live evidence disposition

`completed-scorecard-cases.json` copies the three relevant original failed rows from the completed 20260910T063444Z scorecard, with the source hash. No result was regraded.

The final Spanish category row confirms all five delivered cybersecurity companies and all their reasons reached the judge. Its sole rationale is that cache class movers means the requested category was movers. The repair removes that internal classification from future judge inputs while retaining the semantic evidence.

The final Costco row retains WMT/TGT/AMZN/KR/DG, every explanatory reason, the unsourced/general-knowledge marker, and the actual "closest competitors" sentence. Dollar General's category fit and that stronger ranking claim remain independent relevance critiques. Its separate conflation of resolver verification with current-source grounding is also outside this cache-only payload change. Removing cache metadata does not establish a Costco pass; the historical failure remains recorded.

The final IPO row retains a completed declared result with TLACU as subject and JTTT as peer plus delivered single/versus actions. Its complete historical bound effect was not retained. The new controlled fixture proves the observer omission through the existing canonical sidecar/action builders; it does not manufacture or regrade the missing historical effect.

All processes ended. Source/tests are frozen for parent review; no commits or provider calls were made.

Parent review follow-up: the existing model-citation test now captures the actual serialized judge request and explicitly asserts `citation_origin="model"`, the unchanged URL, `source=null`, and all four `source_period` values. The final 378-test mocked gate passed after these assertions. Existing rejected/disabled/unavailable judge controls still block the gate; actual model behavior under the changed payload remains unmeasured and is reserved for parent-owned targeted validation.
