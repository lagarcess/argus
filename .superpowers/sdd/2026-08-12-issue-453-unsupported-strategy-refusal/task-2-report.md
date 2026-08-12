# Task 2 report: focused unsupported-strategy repair

## Files changed

- `src/argus/agent_runtime/interpreter/focused_extraction.py`
- `src/argus/agent_runtime/llm_interpreter.py`

No test correction was required. The existing issue-453 regressions expressed
the intended behavior before production code changed.

## RED

Command:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py -q -k 'issue_453 or supported_strategy_capability'
```

Result: `2 failed, 6 passed, 72 deselected in 2.62s`.

The bare Coca-Cola unsupported verdict did not call
`FocusedStrategyExtraction`. The pending `$500` response also did not call it
and retained the unvalidated acknowledgment.

## GREEN

Command:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py -q -k 'issue_453 or supported_strategy_capability'
```

Result: `8 passed, 72 deselected in 2.37s`.

Commands:

```bash
poetry run ruff format src/argus/agent_runtime/interpreter/focused_extraction.py src/argus/agent_runtime/llm_interpreter.py
poetry run ruff check src/argus/agent_runtime/interpreter/focused_extraction.py src/argus/agent_runtime/llm_interpreter.py
git diff --check
```

Results: `2 files reformatted`; `All checks passed!`; `git diff --check` was
clean.

## Design reasoning

Constraint-free unsupported requests can now use focused extraction only when
the current message has material execution evidence. With active strategy
context, the repair additionally needs an actual requested field. This remains
an admission predicate only: the focused LLM schema decides whether the text is
a testable strategy.

A bare constraint-free unsupported answer to a pending requested field no
longer satisfies the required-shape check when the current message contains
material execution evidence. That lets the existing focused repair run. Its
result retains the pending artifact as the base draft and is labelled as an
`answer_pending_need`, so the focused `$500` extraction is a typed capital
update rather than a new strategy or an acknowledgment.

Typed unsupported constraints still bypass this new constraint-free path. The
existing capability-conflict audit remains responsible for genuine unsupported
or custom strategy logic.

## Self-review

- No regex, phrase list, locale gate, or deterministic strategy classifier was
  added.
- No raw-value projection, bounds, locale, API, environment, browser, release,
  or evidence code changed.
- The focused test gate covers DCA repair, pending capital update, and supported
  capability recovery.
- The final diff contains only the two owned production files and this report.

## Concerns

None for Task 2. Full backend and browser coverage belong to the parent issue
lane and were not run in this focused subtask.

## Fix round 1: active context continuity gate

### RED

Command:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py -q -k 'active_context_without_requested_field'
```

Result: `1 failed, 80 deselected in 1.43s`.

The noncanonical-text early return admitted a focused repair when an active
strategy snapshot lacked `requested_field`.

### GREEN

Commands:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py -q -k 'active_context_without_requested_field'
poetry run pytest --no-cov tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py -q -k 'issue_453 or supported_strategy_capability'
poetry run ruff format src/argus/agent_runtime/interpreter/focused_extraction.py src/argus/agent_runtime/llm_interpreter.py tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py
poetry run ruff check src/argus/agent_runtime/interpreter/focused_extraction.py src/argus/agent_runtime/llm_interpreter.py tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py
git diff --check
```

Results: `1 passed, 80 deselected in 0.97s`; `9 passed, 72 deselected in
2.34s`; `1 file reformatted, 2 files left unchanged`; `All checks passed!`;
`git diff --check` was clean.

### Design and self-review

The active-context gate now runs before the noncanonical early return, so every
unsupported-request repair requires a real `requested_field` and material
current-turn evidence when an active strategy exists. Fresh no-context DCA
repair and typed capability-conflict behavior remain unchanged. The new
regression asserts the exact predicate is false for an active snapshot without
`requested_field`. No parsing, locale, or response-copy behavior was added.
