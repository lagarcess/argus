# Issue #483 Untouched-Base Evidence

## Source and isolation

- Integration source: `bd96746f6f4c8d7948b6b6e5cec6d1113450847b`
- Source includes merged PR #479 and is both the original worker base and the fetched `origin/codex/private-alpha-next` head used for diagnosis.
- Worker: `codex/issue-483-resolved-state`
- Python: `3.10.20`
- Traffic class for live replay: `guest`
- No `.env` or `web/.env.local` file was created or edited. The protected environment was loaded process-locally while the current directory remained this isolated worker.
- Workflow execution was disabled, so no backtest, deploy, or durable product write ran.

## Deterministic contradiction

The untouched stage boundary was given a complete DCA strategy with KO, monthly cadence, a five-year date range, and a 13,000 recurring amount. The interpretation also carried `provider_context_incomplete_asset_mentions`, matching the live route receipt.

The stage returned all of these facts at once:

- outcome: `needs_clarification`
- canonical asset: `KO`
- missing field: `asset_universe`
- assistant path: acknowledgment facts included KO while the next requested field was the asset

This proves the contradiction is typed state, not only bad wording.

## Real interpreter Guest baseline

The real OpenRouter interpreter and live Alpaca asset catalog replayed the first-contact Guest conversation before code changes.

### English

1. User: `What if I had bought Coca-Cola every month for five years?`
2. Argus: `How much should I use?`
3. User: `use 13,000 pesos`
4. Result: clarification asked which asset to test.

Final typed state still contained:

- strategy: `dca_accumulation`
- asset: `KO`
- asset class: `equity`
- cadence: `monthly`
- recurring amount: `13000`
- five-year date range

The response intent facts contained KO while `requested_fields` contained `asset_universe`. The second turn carried `provider_context_incomplete_asset_mentions`.

### es-419

1. User: `¿Qué habría pasado si hubiera comprado Coca-Cola cada mes durante cinco años?`
2. Argus backend fallback: `How much should I use?`
3. User: `usa 13.000 pesos`
4. Result: clarification asked which asset to test.

Final typed state again contained KO, monthly cadence, the five-year range, and amount `13000`, while requesting `asset_universe`. The fallback asset extraction also treated `usa` as an ambiguous asset-like value with candidates `TDAY` and `USAC`. This is evidence that a second extractor, not the canonical pending strategy, owned the next question.

### Diagnostic cost

Provider-reported cost across the four baseline turns was `$0.10764539999999999`:

| Turn | Cost |
| --- | ---: |
| English opening | `$0.0313566` |
| English amount answer | `$0.02438905` |
| es-419 opening | `$0.02618195` |
| es-419 amount answer | `$0.0257178` |

This is diagnostic baseline spend, not the accepted post-fix live-run cost.

## RED invariant

Command:

```bash
poetry run pytest \
  tests/agent_runtime/test_provider_asset_ownership.py::test_valid_empty_asset_extraction_stops_model_fallback \
  tests/agent_runtime/test_issue_483_resolved_state.py \
  -q --no-cov
```

Result: `3 failed, 4 passed in 4.61s`.

All three failures showed the same structural breach. A valid empty primary asset extraction called both `primary/model` and `fallback/model`, but the invariant permits only the successful primary result. The broader field invariant passed for asset, capital, date range, and cadence, confirming that normal stage recomputation already derives those questions from canonical strategy requirements. The defect is the preflight's false failure signal, which injects a special incomplete-asset blocker before that recomputation.

The first RED node was initially placed beside the provider-ownership suite. It was consolidated into `test_issue_483_resolved_state.py` before delivery because the modularity budget rejected further growth in the older provider-ownership file. The bilingual parameterized test in the dedicated module preserves the same mutation check.
