# Argus Production Readiness Audit

Status: active for `codex/production-readiness-gap-implementation`
Date: 2026-05-05

## Baseline Verification

Before implementation changes, the branch baseline passed:

- `poetry run ruff check .`
- `poetry run pytest tests\agent_runtime tests\test_chat_backtest_state_machine.py -q`
- `cd web; bun test __tests__`

## Product Gaps Closed In This Branch

- Deterministic clarification copy is gated so raw fields and enums do not become the primary assistant voice.
- Thin or stale LLM outputs are rejected or recomposed from current state.
- Confirmation and result actions are separated; Save Strategy belongs inside the result card.
- Conversation reload and history paths hydrate structured cards and latest run metadata.
- Provider truth supports `equity`, `crypto`, and `currency_pair`, with Kraken public REST for currency pairs and crypto fallback.
- Indicator execution is controlled by an executable registry instead of assuming every discovered indicator can run.
- Result cards use a clearer metric display policy, preserve multi-symbol universe truth, and include charted context.

## Supabase Table Usefulness

The current public schema contains:

- `profiles`: product preferences, onboarding, admin flag.
- `conversations`: thread ownership and resumability.
- `messages`: canonical chat history and card metadata.
- `strategies`: saved executable ideas shown in the Strategies surface.
- `collections`: deferred launch UI, still useful as a feature-flagged organizational model.
- `collection_strategies`: deferred launch UI, required when collections return.
- `backtest_runs`: immutable result truth, including chart and trade payload columns.
- `feedback`: launch user-listening surface.
- `usage_counters`: launch safety and quota control.

No tables should be dropped for this branch. Collections should be hidden behind a launch feature flag, not removed from schema.

## Planned Schema Delta

- Extend asset-class checks from `equity | crypto` to `equity | crypto | currency_pair`.
- Keep `backtest_runs.chart` and `backtest_runs.trades` as the result-card chart payload source.
- Do not add embedding/vector tables in this branch.

## External Provider Truth

- Alpaca remains the primary equity and crypto asset availability provider.
- Kraken public REST complements coverage for currency pairs and crypto fallback.
- Kraken OHLC is capped at 720 recent candles per request, so requests beyond that window must be clarified or shortened instead of silently executed.

## Design Constraint Notes

- Charted result cards are an approved product override to the older Alpha note that avoided charts.
- Charts must stay calm, flat, theme-aware, and secondary to the conversational result moment.
- Save Strategy belongs inside the result card only, not the confirmation card.
- TradingView Lightweight Charts attribution must remain visible wherever the result chart renders.
- Confirmation and result cards use distinct restrained reveal animations. Positive and negative result animations differ without becoming decorative noise.

## Acceptance Boundary

This branch does not make embeddings part of launch readiness. Supabase structured state, run metadata, saved strategies, provider catalogs, and keyword search are the launch path. Add pgvector later only after semantic recall becomes a real product need.
