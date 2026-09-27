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
- `derive.py` holds the recorded-fact types, the domain tables and the pure
  reads: balance, observation gaps, activity totals, and position with
  coverage. Nothing derived is stored.
- `model.py` is the in-memory write side: accounts, drafts, review issues,
  previews, idempotent confirmation, corrections and removal. Every operation
  builds a new state and then swaps it in.
- `scenarios.py` holds the named acceptance scenarios and the evidence writer.

The model imports only the standard library, babel, and
`tests.synthetic_ingestion.extract.load_input`. It makes no network or model
calls. The clock and the id sequence are injected.

## Run the tests

From the repository root:

```bash
python -m pytest tests/financial_recording -q --no-cov -p no:cacheprovider
```

## Regenerate the evidence

The committed evidence file is
`docs/reports/evidence/financial-recording/scenarios.json`. A test fails when it
differs from the model's output. After you change the model, regenerate it:

```bash
python -m tests.financial_recording.scenarios \
  --write docs/reports/evidence/financial-recording/scenarios.json
```
