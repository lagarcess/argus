# Research-to-test rail evidence (#377)

Lane: `claude/research-to-test-rail`, base `2fc7dec3` on
`codex/private-alpha-next`. Spec:
`docs/superpowers/specs/2026-08-07-research-to-test-rail.md`.

## Live coverage probes (`probes/`)

Real Perplexity Agent API responses captured 2026-08-07 during the build,
because the spec instructs evidence over documentation (section 5). Raw JSON,
one file per probe.

Findings that shaped the implementation:

- `equity_control_quote.json`: the documented fast configuration
  (`max_steps=1`) returns zero `finance_search` invocations even for AAPL;
  the first step is consumed by a `skill_loaded` event and the model answers
  "I can't retrieve live market data right now."
- `equity_steps2.json`: `max_steps=2` grounds correctly (one invocation,
  AAPL close 312.41 on 2026-08-06). The shipped fast config uses 2 and the
  deviation is documented in `src/argus/domain/research/config.py`.
- `equity_steps_default.json`: omitting `max_steps` also fails to invoke the
  tool, so the default is not permissive.
- `crypto_btc_steps3.json`: the ticker lookup resolves "Bitcoin" to BTCUSD,
  but the model reports plain `BTC` misresolving to the Grayscale Bitcoin
  Mini Trust ETF. Crypto quotes through finance_search would risk quoting
  the wrong instrument; the rail answers crypto from Argus's own Kraken-backed
  data instead.
- `fx_eurusd_steps3.json`: `EURUSD=X` returns an empty quote payload and the
  ticker lookup returns NOT_FOUND. FX is genuinely uncovered; same honest
  degradation path.
- `peers_netflix_steps3.json`: peers arrive as model knowledge verified
  through `tickers_lookup` batches (DIS, WBD, CMCSA, GOOG, FOX all
  ticker-verified) plus a `profile` grounding for the anchor.
- `etf_spy_constituents_steps3.json`: `etf_holdings` works fully (504
  holdings with weights).
- `background_thorough_nflx_dis.json`: background mode lifecycle observed
  queued -> in_progress -> completed in 21.8s for a 10-step opus comparison;
  submit returned in 0.22s.

## Flag-off byte identity (`flag-off-checksum/`)

Cross-commit proof, not an assertion. `scripts/qa/research_rail_flag_off_checksum.py`
drives three deterministic chat turns (educational, market-stats, plain
follow-up) through the real `/chat/stream` surface with
`ARGUS_RESEARCH_RAIL_ENABLED` off and a deterministic injected interpreter,
then hashes the canonicalized stream frames, persisted transcript, and usage
payloads (volatile identifiers and timestamps canonicalized, all else exact).

- `baseline.json`: run at `2fc7dec3` (the integration tip this lane grew
  from), digest `55bb1b89ce5493c5e4f5c2374b5e043b24eb792e499676344c64f9dcef91b8b7`.
- `head.json`: run at the lane's final code head (fc998983; the only
  commit after it is this evidence refresh, which is docs-only), digest
  `55bb1b89ce5493c5e4f5c2374b5e043b24eb792e499676344c64f9dcef91b8b7`.

The digests are identical. Re-proven once more after the Codex review fixes
(operation_scope serialization, thorough caching, sidecar-anchored peers):
the harness reproduces the same digest at that head.

## Browser QA (`browser/`)

Bilingual screenshots; see the PR body for the walk-through. The peer flow
frames (04-06) use a server-seeded pending card so the offers exist
deterministically; every render and interaction in them is the real UI
against the real endpoint. 00 is the flag-off entry surface, byte-identical
to integration. The organic journeys (01-03, 06-09) are live provider turns.
