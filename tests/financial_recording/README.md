# Financial recording reference model

This package is an executable reference model for a PROPOSED
financial-recording contract. It is test-only. It is not a production ledger,
and nothing in `src/` or `web/` imports it. A test enforces both rules.

The model answers one question. If the contract works this way, what do
balances, gaps, spending, income and positions look like in the named
scenarios?

## Layout

- `money.py` validates currency codes against babel (CLDR) and parses decimal
  strings into integer minor units. It never rounds user input.
- `catalog.py` holds the domain tables: account natures, leg signs, refundable
  account types and the default category catalog with stable ids.
- `derive.py` holds the recorded-fact types and the pure reads: the inclusion
  rule, balances, recorded and remaining differences, totals, positions with
  coverage, standing, space scopes and plan occurrence status.
- `review.py` computes review issues. Issues are never stored.
- `model.py` is the in-memory write side: accounts, drafts, previews,
  idempotent confirmation, corrections, removal, restore, space moves,
  categories and expectations. Every operation builds a new state and then
  swaps it in.
- `scenes.py` is the driver every scenario uses. A production driver with the
  same methods can run the same scenarios against the real API.
- `scenarios.py` and `scenarios_lifecycle.py` hold the named acceptance
  scenarios and the evidence writer.

The model imports only the standard library, babel, and
`tests.synthetic_ingestion.extract.load_input`. It makes no network or model
calls. The clock and the id sequence are injected.

## Run the tests

From the repository root:

```bash
poetry run python -m pytest tests/financial_recording -q --no-cov -p no:cacheprovider
```

## Regenerate the evidence

The committed evidence file is
`docs/reports/evidence/financial-recording/scenarios.json`. A test fails when it
differs from the model's output. After you change the model, regenerate it:

```bash
poetry run python -m tests.financial_recording.scenarios \
  --write docs/reports/evidence/financial-recording/scenarios.json
```
