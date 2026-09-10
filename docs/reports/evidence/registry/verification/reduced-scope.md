# Registry scope reduction

The founder's correction retains the registry, executable dispatch, editable
inputs and chat cards, and removes the public receipt/excerpt surface.
Integration `34866139861a5f06a3572edb2533bc42733371e8` is already an ancestor
through normal merge `2c593c8d08c5c152fbfa8dc77c1b3d816f11f35c`. No rebase or
additional reconciliation of public receipt code was performed for this reset.

## Reduced diff

All 45 paths in [the reset manifest](public-surface-reset.json) match integration
exactly, including absence where integration has no file. This includes every
explicitly named public route, schema, renderer, helper, test and migration,
plus the public selection adapters and tests added during reconciliation.
The three registry receipt migrations are gone. The shipped header share panel
is back in its integration location; the registry's chat/progress/recompute
hunks are retained. Public locale additions, fixture writers and OpenAPI
changes were removed; only the existing private recompute endpoint remains as
an OpenAPI addition. Runtime regeneration is pending the import boundary below.

The 19 implementation files explicitly listed to keep are byte-identical to
the pre-reset worker. The manifest records their hashes, including
`stages/tool_execution.py` and `tool-result-recompute.ts`. `evidence-visual.ts`
is retained because the preserved chat card imports it. No financial
calculation was added, and no question-to-calculation mapping was introduced.

| Diff against integration | Before reset | Reduced tree |
| --- | ---: | ---: |
| Python application paths (`src/`) | 95 | 85 |
| Web paths, including tests | 55 | 32 |
| Python test paths (`tests/`) | 84 | 79 |
| Database migrations | 3 | 0 |

These counts are from the tracked tree before adding this report and manifest.
The large historical scorecards are retained unchanged; they remain failed
measurement evidence. Earlier receipt reconciliation reports describe removed
work and do not establish acceptance of this reduced tree.

## Dependencies exposed by the requested reset

1. `src/argus/agent_runtime/tools/backtest_presentation.py:9` imports
   `backtest_receipt_facts` from `domain/public_excerpts.py`. Integration has no
   such helper. The preserved presenter is loaded by `registered_backtest.py`
   and background result projection. The removed helper has not been restored.
   This is a dependency of the current implementation, not a requirement to
   publish general tool results in this lane.
2. The explicitly removed `src/argus/llm/tool_call_receipts.py` contains internal
   per-call model cost attribution. `src/argus/llm/openrouter.py:38` imports it,
   and the preserved `interpreter/backtest_calls.py:40` consumes its re-export.
   The file is absent as requested; those preserved imports now lack their
   dependency.

Work stops at this boundary rather than modifying the preserved implementation
or restoring the excluded files. General tool publication remains a follow-up
against the shipped receipt contract. These import gaps prevent a green runtime
or CI claim; no post-reset suite, browser capture, provider measurement or review
round was started. The existing open review thread remains unresolved.

## Verification and cleanup

Git object comparisons confirm all reset paths, all 19 protected files, and
integration ancestry. `git diff --check` passes. This is source comparison,
not runtime acceptance. No merge to integration, deployment, hosted database
operation or public flag change occurred.

The follow-up local database work stopped before its test suites started.
Both registry-owned stacks and their temporary credentials are removed; the
other preexisting local project was preserved. Uncommitted receipt evidence was
moved outside the repository. All participating agents are idle.
