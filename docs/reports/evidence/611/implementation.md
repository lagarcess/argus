# Research instrument identity, issue 611

## Cause and change

An exact provider lookup resolves BTC to the Grayscale equity ETF before consulting the catalog. Research subject and peer lookups discarded the query's class hint, while the peer filter accepted only equities and the comparison composer combined classes.

Research now uses `resolve_asset_candidate` with the available class. Its opt-in ambiguity policy withholds an unhinted cross-class symbol. Default chat resolution is unchanged. Comparisons filter to the anchor class, and both inline and background publication refrain from replacing an unresolved named subject with a peer. Background requests retain requested symbols and the hint so an empty offer uses the existing honest no-next line.

## Caller inventory

Changed plain resolver callers that build Try next offers:

- `research_answer._resolved_subjects`: carries `ResearchQueryExtraction.asset_class_hint`.
- `research_rows._resolve_bounded`: carries the subject class from `verified_peers`; both inline and background publishers pass it.
- `next_experiments._peer_is_grounded`: carries the result's existing class and checks the resolved class before offering a prebaked peer.

Other plain resolver callers, unchanged:

- `resolution.resolve_asset_candidate`: the shared class-aware owner itself.
- `api.routers.conversations._resolved_peer_identities`: revalidates a selected confirmation peer after a tap; it does not compose Try next rows.
- `llm_interpreter._resolve_asset_candidate` and `stages.interpret._resolve_asset_candidate`: compatibility paths for injected test resolvers; normal chat delegates to the shared owner.
- `stages.execute._resolve_benchmark_symbol`: benchmark selection, two call sites.
- `domain.market_data.assets.warm_asset_universe`: provider warmup.
- `discovery/model_knowledge.py`: a docstring mention, not a call.

## Deterministic evidence

`tests/research/test_research_asset_identity.py` uses a provider-shaped catalog containing both BTC the crypto and BTC the ETF. Only the external exact-ticker lookup is replaced to return the ETF; the catalog search and class-aware resolver are real. Price history uses fixtures.

The initial run failed 9 cases and passed 2, reproducing the wrong Bitcoin label, ambiguous BTC offer and mixed-class comparisons. The completed test file covers English and Spanish identity, explicit ETF, bare BTC, ETF and Ethereum peers, Bitcoin plus Apple, unchanged equity comparisons, inline/background publication, result peer grounding, and crossover rows. Real confirmation assembly preserves BTC plus its class for both instruments after a controlled structured interpretation.

Limit: tap text remains unchanged, as required by the model-facing-text restriction. The confirmation test controls the model's class read; it is not a live browser or live-model guarantee about interpreting the bare ticker. No paid calls were made.

Original integration base: `350e3dca8f573f5dfd61f1f753d8ed16a2724c9e`.
Final reconciliation, CI and the single Codex review outcome belong in the terminal PR audit after review returns.
