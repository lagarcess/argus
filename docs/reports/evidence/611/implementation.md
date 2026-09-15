# Research instrument identity, issue 611

## Cause and change

An exact provider lookup resolves BTC to the Grayscale equity ETF before consulting the catalog. Research subject and peer lookups discarded the query's class hint, while the peer filter accepted only equities and the comparison composer combined classes.

Research now uses `resolve_asset_candidate` with the available class. Its opt-in ambiguity policy withholds an unhinted cross-class symbol. Default chat resolution is unchanged. Comparisons filter to the anchor class, and both inline and background publication refrain from replacing an unresolved named subject with a peer. Background requests retain requested symbols and the hint so an empty offer uses the existing honest no-next line.

## Resolver caller audit

Scope: all production `src/argus` calls to `resolve_asset`, including its `resolve_market_asset` and injected `resolve_asset_func` aliases. The second table follows the `classify_symbol` wrapper so execution and quote callers are visible too. Tests, imports, exports and docstring mentions are not runtime calls.

| Caller | Asset class available? | Disposition |
| --- | --- | --- |
| `research_answer._resolved_subjects` | Yes, research query hint when supplied | Fixed: shared `resolve_asset_candidate` with hint and strict cross-class ambiguity handling. |
| `research_rows._resolve_bounded` via `verified_peers` | Yes, subject class | Fixed: shared owner with hint; related names and comparisons stay in the subject class. Both inline and background publishers pass the class. |
| `next_experiments._peer_is_grounded` | Yes, result class | Fixed: shared owner with hint and a same-class check before offering the result's peer row. |
| `conversations._resolved_peer_identities`, selected-add call | Yes, stored peer identity and owning confirmation | Fixed: removed ticker resolution. Selects the stored symbol, name and class carried by the offered row. New requests carry symbol and class; the server checks the stored offer. |
| `conversations._resolved_peer_identities`, remaining/Undo row call (formerly near line 1191) | Yes, stored offers and confirmation adjustment | Fixed: uses the same stored-identity selection for remaining offers and restored offers. Legacy symbol-only rows derive class from their owning confirmation, without a lookup. |
| `resolution.resolve_asset_candidate` (`resolve_market_asset` alias) | Optional caller hint | Shared owner. Added opt-in research ambiguity refusal; its existing hinted resolution remains the only class-aware resolver. Default chat policy unchanged. |
| `llm_interpreter._resolve_asset_candidate` | Yes, optional hint | Unchanged: plain call is the injected-test-resolver compatibility branch. Normal chat delegates to the shared class-aware owner. |
| `stages.interpret._resolve_asset_candidate` | Yes, optional hint | Unchanged: same injected-test-resolver compatibility branch; normal chat delegates to the shared owner. |
| `stages.execute._resolve_benchmark_symbol`, currency-pair branch | Yes, strategy class is currency pair | Unchanged execution path: plain symbol lookup. Reported below. |
| `stages.execute._resolve_benchmark_symbol`, final fallback | No supported class in this branch | Unchanged execution fallback: plain symbol lookup. Equity and crypto use their existing default-benchmark branches before this fallback. |
| `domain.market_data.assets.warm_asset_universe` | No class parameter for required symbols | Unchanged provider warmup. |
| `domain.backtesting.config.classify_symbol` (`resolve_asset_func` injection) | No class parameter | Unchanged classless wrapper; callers with known classes are enumerated below. |

### Classless wrapper callers outside Try next

| Caller | Asset class available? | Disposition |
| --- | --- | --- |
| `domain.engine.classify_symbol` | No class parameter | Unchanged wrapper that injects `resolve_asset` into `config.classify_symbol`. |
| `domain.engine_launch.adapter.validate_request_symbols` | Yes, `request.asset_class` | Unchanged execution validation. Starts classless, then tries the declared class after a mismatch and enforces agreement. |
| `domain.engine_launch.adapter.validate_request_benchmark` | Yes, `request.asset_class` | Unchanged execution validation with the same mismatch recovery. |
| `domain.backtesting.config.normalize_backtest_config`, symbols | Yes, optional payload class | Unchanged execution normalization. Classless classification can reject a hinted collision as `asset_class_conflict` or `mixed_asset_not_supported`. |
| `domain.backtesting.config.normalize_backtest_config`, benchmark | Yes, selected run class | Unchanged execution normalization. Classless benchmark classification can reject a collision as `invalid_benchmark_symbol`. |
| `api.backtest_service.ensure_same_asset_or_raise` | No class parameter; its `prepare_run_from_payload` and `api.routers.backtest._validate_asset_class` callers have payload class | Unchanged backtest admission helper. Classless classification precedes the callers' class checks. |
| `domain.backtest_run_builder.build_backtest_run_from_result` | Yes, resolved strategy is available | Unchanged result persistence helper. Reclassifies the first symbol without class and falls back to equity on an exception. `api.chat.persistence` delegates to this owner; it adds no lookup. |
| `agent_runtime.knowledge_answer._market_stats_answer` | Draft can carry class; lookup uses only symbol | Unchanged quote/market-stat lookup. Its generic Try next sidecar does not use this resolved identity to compose an instrument row. |
| `agent_runtime.answer_calculation.latest_market_close` | No class parameter | Unchanged quote lookup, outside row and confirmation-peer construction. |

**Execution report:** classless re-resolution remains in the execution, admission, normalization and result-persistence paths listed above. The adapter has declared-class recovery; the normalizer and persistence helper do not. These paths were inspected and left unchanged under the explicit scope restriction. No claim is made that this PR fixes execution-side ticker collisions.

`assets.resolve_asset` is the underlying implementation. `domain.engine` and `domain.market_data.__init__` also re-export it. `discovery/model_knowledge.py` mentions it only in a docstring. None is an additional lookup site.

## Deterministic evidence

`tests/research/test_research_asset_identity.py` uses a provider-shaped catalog containing both BTC the crypto and BTC the ETF. Only the external exact-ticker lookup is replaced to return the ETF; the catalog search and class-aware resolver are real. Price history uses fixtures.

The initial run failed 9 cases and passed 2, reproducing the wrong Bitcoin label, ambiguous BTC offer and mixed-class comparisons. The completed test file covers English and Spanish identity, explicit ETF, bare BTC, ETF and Ethereum peers, Bitcoin plus Apple, unchanged equity comparisons, inline/background publication, result peer grounding, and crossover rows. Real confirmation assembly preserves BTC plus its class for both instruments after a controlled structured interpretation.

Limit: tap text remains unchanged, as required by the model-facing-text restriction. The confirmation test controls the model's class read; it is not a live browser or live-model guarantee about interpreting the bare ticker. No paid calls were made.

Original integration base: `350e3dca8f573f5dfd61f1f753d8ed16a2724c9e`.
Final reconciliation, CI and the single Codex review outcome belong in the terminal PR audit after review returns.

## Confirmation-peer review fix

The first review reproduced a 422 when a stored BTC crypto offer was resolved again as the ETF. The action now carries the stored symbol and class through the frontend handler and API request. The endpoint selects the server-stored identity, including its name; add, add-all, remaining rows and Undo perform no new ticker resolution. Older symbol-only requests and rows use their owning confirmation's class. Client class substitution and unoffered identities are rejected.

The regression was red in all six original endpoint cases and in the frontend row-action test. The completed endpoint matrix covers both BTC classes, single/add-all/legacy requests, legacy stored rows, remaining rows, Undo and identity tampering. The frontend transport test drives the real row action, confirmation handler and API client through a mocked HTTP boundary. No live browser, provider, or paid-model call was used.

Focused completion evidence: 10 endpoint identity cases pass; the earlier combined owner run passed 63 cases before the four added equity/legacy-row cases. The complete frontend suite passes 1,989 tests, the production build passes, backend Ruff passes, frontend lint has zero errors (eight existing warnings), and the modularity budget passes. The changed peer-selection code does not branch on strategy type or alter strategy parameters; canonical confirmation preparation still owns strategy and coverage validation.
