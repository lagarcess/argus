# Interpreter payload after a result

On a turn after a completed run, the interpreter prompt embedded the whole stored
result reference: the result card with its tool cards, the chart series twice,
markers and trades. The fix gives the prompt only the run's typed configuration and
an explicit list of headline facts, as JSON, from one owner
(`src/argus/agent_runtime/interpreter/latest_result_context.py`) that the
latest-result routing audit also reads.

## Live proof

One turn through the app's own runtime (`argus.api.state.build_agent_runtime_workflow`),
live providers, asking "Why did it fall so much along the way?" about the same stored
result: DOCN buy and hold from September 1, 2023, saved by the local app on
2026-09-11 (168,787 characters of reference metadata).

| | Main interpreter call, prompt tokens | Interpretation cost | Turn cost |
|---|---|---|---|
| [Before](before.json) | 94,086 | $0.1252 | $0.1390 |
| [After](after.json) | 11,216 | $0.0211 | $0.0351 |

Both turns answered with 5 returned sources and three related questions. The two
small audit calls grew slightly (1,457 to 1,663 and 542 to 749 prompt tokens) because
the routing audit now reads the same fact list as the main prompt.

Provenance: "before" ran at `fe8d55dd` with the new module present but never imported
(`latest_result_context_module_loaded: false`); "after" ran on the uncommitted fix that
the commit containing this file records. Billed for both turns: $0.1741.
Driver: [after_result_turn_cost.py](after_result_turn_cost.py).
