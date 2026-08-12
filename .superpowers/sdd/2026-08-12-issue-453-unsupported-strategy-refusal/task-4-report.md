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

## Fix round 1: fail closed on malformed bound pairs

Review found that backend finiteness checks did not reject reversed pairs and
could retain the valid half of a non-finite pair. The clarifier voice projection
also copied both numbers independently. This could persist or voice a misleading
capital range.

### RED

```text
poetry run pytest --no-cov tests/agent_runtime/test_conversation_stages.py -q -k 'invalid_starting_capital_bounds or clarifier_drops_invalid_starting_capital_bound_pairs'
```

Result: exit 1, 6 failed, 85 deselected. Reversed bounds rendered and persisted;
non-finite pairs retained one bound; all three malformed pairs reached clarifier
context.

```text
bun test web/__tests__/chat-recovery-display.test.ts --test-name-pattern 'malformed starting-capital'
```

Result: exit 1, 2 passed, 1 failed. The non-finite maximum was incorrectly
degraded into valid floor copy.

### GREEN

```text
poetry run pytest --no-cov tests/agent_runtime/test_conversation_stages.py -q -k 'invalid_starting_capital_bounds or clarifier_drops_invalid_starting_capital_bound_pairs'
```

Result: exit 0, 6 passed, 85 deselected.

```text
bun test web/__tests__/chat-recovery-display.test.ts --test-name-pattern 'malformed starting-capital'
```

Result: exit 0, 3 passed, 32 filtered out, 6 assertions.

Final required commands:

```text
poetry run pytest --no-cov tests/agent_runtime/test_validation_failure_copy.py tests/agent_runtime/test_conversation_stages.py -q -k 'issue_453 or raw_value or starting_capital'
bun test web/__tests__/chat-recovery-display.test.ts
```

Result: backend exit 0 with 16 passed and 85 deselected; Bun exit 0 with
35 passed and 106 assertions.

```text
poetry run pytest --no-cov tests/test_i18n_coverage.py -q
poetry run ruff format --check src/argus/agent_runtime/clarification_contract.py src/argus/agent_runtime/llm_clarifier.py tests/agent_runtime/test_conversation_stages.py
poetry run ruff check src/argus/agent_runtime/clarification_contract.py src/argus/agent_runtime/llm_clarifier.py tests/agent_runtime/test_conversation_stages.py
cd web && bun run lint lib/chat-recovery-display.ts __tests__/chat-recovery-display.test.ts
git diff --check
```

Result: locale parity 4 passed; Ruff format and check passed; targeted ESLint
passed; diff check passed. The first Ruff check found only an import-order issue
in the edited test, which was corrected manually before the repeated clean run.

### Reasoning and self-review

- One backend `validated_starting_capital_bounds` function now owns finite,
  complete, and ordered bound projection for sidecars, fallback copy, and LLM
  voice context.
- A finite minimum with no maximum remains a valid floor. If a maximum is
  present, both values must be finite and `minimum <= maximum`; otherwise the
  entire pair is dropped.
- Web hydration follows the same whole-pair rule and no longer turns an invalid
  maximum into apparently valid floor copy.
- Canonical `$1,000` to `$100,000,000` range copy, typed floor copy, timeframe
  raw-value preservation, and generic raw-value suppression remain unchanged.
- Locale catalogs were not modified in this fix round; parity was rerun and
  remains green.
- Scope audit contains only the two backend owners, backend test, web projection,
  web test, and this report.

No new concerns were found. The previously recorded branch-wide TypeScript
baseline classification is unchanged.

## Fix round 2: keep backend fallback language neutral

Full verification found that the backend fallback still contained runtime
`es-419` branches and that older tests required raw ATR, momentum, and drawdown
phrases in user-facing fallback copy. It also found that the six Task 4
regressions had pushed the watched conversation-stage test module above its
line budget.

### RED

```text
poetry run pytest --no-cov tests/agent_runtime/test_interpret_stage.py::test_interpreter_unavailable_spanish_atr_routes_to_unsupported_recovery tests/agent_runtime/test_unsupported_fallback_honesty.py::test_momentum_generation_failure_fallback_is_capability_honest tests/agent_runtime/test_unsupported_fallback_honesty.py::test_other_unsupported_reasons_never_claim_rule_is_undefined tests/test_spine_guardrails.py::test_issue_154_migrated_surfaces_have_no_runtime_language_gates -q
```

Result: exit 1, 4 failed and 8 passed. The three stale expectations required
raw unsupported prose, and the language guard found the runtime `es-419`
branches in `clarification_contract.py`.

After moving the six regressions into the focused module, the canonical backend
copy regression isolated the production defect:

```text
poetry run pytest --no-cov tests/agent_runtime/test_issue_453_cause_projection.py -q
```

Result: exit 1, 1 failed and 10 passed. The `es-419` input returned Spanish
backend copy instead of the canonical fallback.

### GREEN

Focused projection, complete conversation-stage module, and named stale cases:

```text
poetry run pytest --no-cov tests/agent_runtime/test_issue_453_cause_projection.py tests/agent_runtime/test_conversation_stages.py tests/agent_runtime/test_interpret_stage.py::test_interpreter_unavailable_spanish_atr_routes_to_unsupported_recovery tests/agent_runtime/test_unsupported_fallback_honesty.py::test_momentum_generation_failure_fallback_is_capability_honest tests/agent_runtime/test_unsupported_fallback_honesty.py::test_news_sentiment_generation_failure_fallback_is_capability_honest tests/agent_runtime/test_unsupported_fallback_honesty.py::test_other_unsupported_reasons_never_claim_rule_is_undefined tests/agent_runtime/test_unsupported_fallback_honesty.py::test_future_and_granularity_fallbacks_are_unchanged -q
```

Result: exit 0, 97 passed.

Task 4 exact commands:

```text
poetry run pytest --no-cov tests/agent_runtime/test_validation_failure_copy.py tests/agent_runtime/test_conversation_stages.py -q -k 'issue_453 or raw_value or starting_capital'
bun test web/__tests__/chat-recovery-display.test.ts
```

Result: backend exit 0 with 6 passed and 85 deselected; Bun exit 0 with
35 passed and 106 assertions.

Language guards and locale parity:

```text
poetry run pytest --no-cov tests/test_spine_guardrails.py::test_issue_154_migrated_surfaces_have_no_runtime_language_gates tests/agent_runtime/test_issue_154_s3_recovery_i18n_contract.py::test_s3_backend_surfaces_do_not_reintroduce_runtime_language_gates -q
bun test web/__tests__/locales.test.ts web/__tests__/chat-recovery-display.test.ts
```

Result: language guards exit 0 with 10 passed; frontend locale and recovery
tests exit 0 with 39 passed and 332 assertions.

Static and structural checks:

```text
poetry run ruff format src/argus/agent_runtime/clarification_contract.py tests/agent_runtime/test_conversation_stages.py tests/agent_runtime/test_issue_453_cause_projection.py tests/agent_runtime/test_validation_failure_copy.py tests/agent_runtime/test_interpret_stage.py tests/agent_runtime/test_unsupported_fallback_honesty.py
poetry run ruff check src/argus/agent_runtime/clarification_contract.py tests/agent_runtime/test_conversation_stages.py tests/agent_runtime/test_issue_453_cause_projection.py tests/agent_runtime/test_validation_failure_copy.py tests/agent_runtime/test_interpret_stage.py tests/agent_runtime/test_unsupported_fallback_honesty.py
poetry run python scripts/check_modularity_budget.py
git diff --check
```

Result: Ruff reported all lint checks passed; modularity reported no
violations; diff check passed. Whole-file formatting exposed pre-existing
format drift in the large interpreter-stage test and was not retained. A
focused Ruff lint check was rerun after restoring the parent formatting. The
complete `test_conversation_stages.py` module is now 3,639 lines, below its
3,697-line limit.

### Reasoning and self-review

- Backend fallback now ignores language and emits one canonical English string;
  localized rendering remains owned by the web typed-sidecar projection.
- The shared starting-capital validator remains the only source for fallback,
  sidecar, and clarifier bounds. Valid floor and range behavior is unchanged,
  while reversed and non-finite pairs still fail closed.
- Stale tests now prove raw ATR, momentum, and drawdown prose does not become a
  sentence subject while typed capability copy, options, and symbols survive.
- Dedicated typed timeframe raw value and sentiment/news reason behavior remain
  covered and unchanged.
- All six `test_issue_453_*` blocks were moved without duplication into
  `test_issue_453_cause_projection.py`.
- Locale catalogs were not modified in this fix round. English and es-419
  catalog parity remains green, and every unrelated locale key was preserved.
- Scope audit contains only the owned backend contract, owned backend tests,
  the new focused test module, and this report.

No new concerns were found. The prior branch-wide TypeScript baseline remains
unchanged and was not rerun in this backend-only fix round.

### Post-commit formatting cleanup

The first fix-round commit accidentally retained whole-file Ruff formatting in
`test_interpret_stage.py`. A line-by-line comparison against parent
`33f4c3ad787620f039aae331e30b1128b1cf6261` was used to restore every unrelated
line while keeping only the intended ATR raw-prose assertions. This cleanup is
recorded as a separate commit without amending the first fix-round commit.

## Fix round 3: split focused web recovery regressions

Terminal verification found that `chat-recovery-display.test.ts` had crossed
the repository's 1,000-line modularity capture threshold. This round moved only
the issue #453 generic raw-value, typed starting-capital, and malformed-bound
cases into a focused TypeScript-clean module.

### RED

```text
wc -l web/__tests__/chat-recovery-display.test.ts
poetry run python scripts/check_modularity_budget.py
poetry run pytest --no-cov tests/test_modularity_budget.py -q
```

Result: the existing test was 1,036 lines. The modularity report itself had no
watched-file violation, but the structural capture suite exited 1 with 1 failed
and 7 passed because the newly large test file was not in the watched baseline.

The TypeScript baseline was captured from `web/` before extraction:

```text
bun x tsc --noEmit 2>&1 | awk '/error TS/{total += 1} /__tests__\/chat-recovery-display\.test\.ts.*error TS/{original += 1} /__tests__\/issue-453-chat-recovery-display\.test\.ts.*error TS/{focused += 1} END {print "total_errors=" total; print "chat_recovery_errors=" original; print "focused_issue_453_errors=" focused; exit(total > 0 ? 1 : 0)}'
```

Result: exit 1 with 6,034 total diagnostics, 99 diagnostics attributed to
`chat-recovery-display.test.ts`, and no focused issue #453 file yet.

### GREEN

Focused behavior and structural capture:

```text
wc -l web/__tests__/chat-recovery-display.test.ts web/__tests__/issue-453-chat-recovery-display.test.ts
bun test web/__tests__/chat-recovery-display.test.ts web/__tests__/issue-453-chat-recovery-display.test.ts
poetry run pytest --no-cov tests/test_modularity_budget.py -q
```

Result: the original file is 916 lines and the focused file is 154 lines. Bun
passed all 35 tests across both files with 0 failures. The modularity suite
passed all 8 tests.

Full frontend and static checks:

```text
cd web && bun run lint __tests__/chat-recovery-display.test.ts __tests__/issue-453-chat-recovery-display.test.ts
cd web && bun run test
poetry run python scripts/check_modularity_budget.py
git diff --check
```

Result: targeted ESLint passed; the full frontend suite passed 1,475 tests with
0 failures and 11,117 Bun `expect` calls; modularity reported no violations;
diff check passed.

The TypeScript comparison was rerun with the same counter:

```text
bun x tsc --noEmit 2>&1 | awk '/error TS/{total += 1} /__tests__\/chat-recovery-display\.test\.ts.*error TS/{original += 1} /__tests__\/issue-453-chat-recovery-display\.test\.ts.*error TS/{focused += 1} END {print "total_errors=" total; print "chat_recovery_errors=" original; print "focused_issue_453_errors=" focused; exit(total > 0 ? 1 : 0)}'
```

Result: the known branch baseline remains red with 6,017 total diagnostics.
The original file now has 82 diagnostics and the new focused file has zero.
The measured lane delta is therefore minus 17 overall and minus 17 in the
original file, with no diagnostic moved into or added by the focused module.
The review prompt estimated 18 moved-case diagnostics; the before-and-after
compiler evidence on this exact checkout measured 17.

### Reasoning and self-review

- The seven behavioral cases remain individually named: three generic raw
  values, one canonical numeric range, and three malformed numeric pairs.
- The new file uses simple Bun `test` callbacks, `node:assert/strict`, and one
  minimal catalog translator cast to the exact `TFunction` boundary. It avoids
  the repository's baseline-red Bun matcher and `test.each` types.
- The pre-existing unsupported-symbol and degraded-momentum tests remain in the
  original file with their changed expectations intact.
- Search confirms no issue #453 case remains duplicated in the original file.
- Product source, locale catalogs, browser evidence, environment files, and all
  other tests were not modified.

The only concern is the pre-existing branch-wide TypeScript baseline. This
round reduces its measured diagnostic count and adds zero diagnostics in the
new focused file.
