# Task 4 report: cause-aware recovery projection

## Outcome

Task 4 now projects unsupported recovery from typed causes. Generic recovery
does not use `raw_value` as a sentence subject. Starting-capital recovery carries
typed numeric bounds through the clarification sidecar and renders an explicit
English or es-419 range. Dedicated time-granularity behavior remains unchanged,
and uncategorized extraction still asks what rule to test.

## RED evidence

Before production changes:

```text
poetry run pytest --no-cov tests/agent_runtime/test_validation_failure_copy.py tests/agent_runtime/test_conversation_stages.py -q -k 'issue_453 or raw_value or starting_capital'
```

Result: exit 1, 7 failed, 85 deselected. Six failures showed generic raw values
as sentence subjects. One failure showed starting capital as an unsupported rule
and omitted the `$1,000` floor.

```text
bun test web/__tests__/chat-recovery-display.test.ts
```

Result: exit 1, 28 passed, 3 failed. Each failure rendered a generic raw value
as the localized sentence subject.

After adding the narrow Task 4 regressions, before production changes:

```text
poetry run pytest --no-cov tests/agent_runtime/test_validation_failure_copy.py tests/agent_runtime/test_conversation_stages.py -q -k 'issue_453 or raw_value or starting_capital'
```

Result: exit 1, 9 failed, 85 deselected. The added failures proved missing typed
bounds projection, bilingual range fallback, and starting-capital prompt routing.

```text
bun test web/__tests__/chat-recovery-display.test.ts
```

Result: exit 1, 27 passed, 5 failed. The added failures proved generic momentum
copy still exposed raw text and typed capital bounds did not render.

Final self-review found that the first voice projection removed the dedicated
typed timeframe value together with generic raw text. The narrow regression:

```text
poetry run pytest --no-cov tests/agent_runtime/test_conversation_stages.py -q -k 'issue_453_clarifier_preserves_typed_time_granularity_value'
```

first returned exit 1 with 1 failed and 84 deselected, then returned exit 0 with
1 passed and 84 deselected after the projection preserved `5m` only for the
typed `unsupported_time_granularity` cause.

## GREEN evidence

Final required commands:

```text
poetry run pytest --no-cov tests/agent_runtime/test_validation_failure_copy.py tests/agent_runtime/test_conversation_stages.py -q -k 'issue_453 or raw_value or starting_capital'
```

Result: exit 0, 10 passed, 85 deselected.

```text
bun test web/__tests__/chat-recovery-display.test.ts
```

Result: exit 0, 32 passed, 0 failed, 100 assertions.

Additional checks:

```text
poetry run pytest --no-cov tests/agent_runtime/test_validation_failure_copy.py tests/agent_runtime/test_conversation_stages.py tests/test_i18n_coverage.py -q
```

Result: exit 0, 98 passed.

```text
poetry run ruff format --check src/argus/agent_runtime/clarification_contract.py src/argus/agent_runtime/llm_clarifier.py tests/agent_runtime/test_validation_failure_copy.py tests/agent_runtime/test_conversation_stages.py
poetry run ruff check src/argus/agent_runtime/clarification_contract.py src/argus/agent_runtime/llm_clarifier.py tests/agent_runtime/test_validation_failure_copy.py tests/agent_runtime/test_conversation_stages.py
```

Result: exit 0, four files formatted, all checks passed.

The first final format check identified two files needing mechanical Ruff
formatting. Ruff formatted them, and the repeated format and check commands
returned exit 0.

```text
cd web && bun run lint lib/chat-recovery-display.ts __tests__/chat-recovery-display.test.ts
```

Result: exit 0.

```text
git diff --check
```

Result: exit 0.

The first combined verification command invoked `bun run lint` from the
repository root and returned `Script not found "lint"`. This was an operator
working-directory error. The same targeted lint command was rerun from `web/`
and passed.

## Locale reconciliation

The locale catalogs were edited in place without sorting or bulk formatting.
The edit deleted only
`chat.clarification.unsupported_recovery_with_raw_value` and
`chat.clarification.unsupported_recovery_with_raw_value_for_asset`, then added
matching `starting_capital_range` and `starting_capital_floor` keys in English
and es-419. All unrelated keys, including concurrent additive keys, were
preserved. The repository i18n key and placeholder parity suite passed with
four tests.

## Design reasoning

- `raw_value` remains opaque sidecar metadata for compatibility, but generic
  backend and web rendering never select it.
- Time granularity keeps the existing dedicated typed raw value branch because
  that value is the validated bar-size fact.
- Numeric bounds are copied only for the
  `unsupported_starting_capital` cause and only when values are finite numbers.
  Malformed or reversed bounds fail closed instead of producing misleading copy.
- Starting capital is described as an input range, not as a missing strategy
  capability. Both backend fallback and web hydration use the same typed
  minimum and maximum contract.
- The clarifier voice context removes generic `raw_value` and explanation text,
  plus untyped strategy prose, while preserving typed category, bounds,
  strategy fields, timeframe value, and options.

## Self-review

- Confirmed generic subjects cover model summaries, a strategy phrase, a symbol,
  and a momentum phrase.
- Confirmed uncategorized extraction stays on the existing rule question.
- Confirmed response options and timeframe actions remain green in the full Bun
  file.
- Confirmed the two owned backend modules pass in full, not only under the issue
  filter.
- Confirmed no forbidden or out-of-scope file is modified.
- Confirmed no new or modified user-facing copy uses an em dash.

## Concerns

`cd web && bun x tsc --noEmit` remains red on the branch-wide baseline. The
output contains hundreds of existing `bun:test` matcher and callback typing
errors across the test suite, plus unrelated e2e fixture errors. A filtered
inspection showed no error in the production file
`web/lib/chat-recovery-display.ts`; errors naming the owned test file are the
same existing Bun test-harness typing pattern. Targeted ESLint and the real Bun
test both pass.
