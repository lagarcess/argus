# Argus Conversational Runtime

Status: Active Alpha implementation

Argus treats conversation as the product surface and backtesting as an execution tool. The active `/api/v1/chat/stream` path runs the LangGraph agent runtime with a model-backed interpretation layer before validation, confirmation, execution, persistence, and explanation.

## Runtime Contract

The model proposes meaning. Argus validates it. The user confirms it. The engine executes it.

This separation is intentional:

- LLM interpretation is used for natural language understanding, strategy type inference, structured strategy drafting, ambiguity detection, correction-aware follow-ups, conversational unsupported handling, confirmation wording, and result explanation.
- Deterministic code is used for capability truth, provider availability, asset class validation, required-field gating, same-asset restrictions, execution defaults, benchmark selection, indicator execution specs, backtest execution, result envelopes, persistence, and stream event shape.
- The LLM cannot silently mark unsupported behavior as executable, invent asset availability, change symbols, bypass confirmation, or fabricate result metrics.
- Deterministic fallback cannot become the normal assistant voice. If the LLM fails, Argus may preserve truth internally, but user-facing copy must be natural recovery language rather than raw fields, enums, or starter prompts.

## Voice Boundary

Every user turn is routed by intent and conversation context before slot or field logic can speak.

The runtime rejects assistant responses that are:

- one-word or fragment answers when the user asked for explanation
- stale summaries based on the wrong user turn
- raw internal names such as `asset_universe`, `not specified`, or `requested_field`
- generic starter guidance after a thread already has context

When a response fails this gate, the runtime composes a grounded natural response from the current act, state, and validation result. This keeps deterministic truth in the system without making deterministic scaffolding the product voice.

## Active Layers

1. Conversational intelligence
   - `src/argus/agent_runtime/llm_interpreter.py`
   - Uses OpenRouter through task-scoped client construction and structured output.
   - Preserves raw user phrasing and normalized strategy meaning.
   - Uses bounded model budgets by task so provider defaults cannot request oversized completions.

2. Stateful orchestration
   - `src/argus/agent_runtime/graph/workflow.py`
   - Routes `interpret -> clarify -> confirm -> execute -> explain`.
   - Persists pending and confirmed strategy summaries in the latest task snapshot.

3. Structured strategy contract
   - `src/argus/agent_runtime/state/models.py`
   - Captures strategy type, symbols, asset class, date range, cadence, entry/exit logic, sizing, risk rules, assumptions, unsupported constraints, and refinement metadata.

4. Validation and capability truth
   - `src/argus/agent_runtime/stages/interpret.py`
   - `src/argus/agent_runtime/capabilities/contract.py`
   - `src/argus/domain/market_data/*`
   - Alpaca `/v2/assets` is the primary equity and crypto availability source through `resolve_asset`.
   - Kraken public REST complements Argus for currency pairs and crypto fallback. Kraken OHLC is limited to the latest 720 candles per interval, and requests outside that window must recover conversationally instead of pretending data exists.
   - `src/argus/domain/indicators/registry.py` is the executable indicator contract. pandas-ta discovery can expose draft-only indicators, but an indicator is executable only when its spec defines parameters, output selector, bounds, defaults, and threshold formatting.

5. Execution truth
   - `src/argus/agent_runtime/tools/real_backtest.py`
   - `src/argus/agent_runtime/stages/execute.py`
   - Runs real supported backtests and returns the same result envelope used by the UI.

6. UI integration
   - `web/components/chat/ChatInterface.tsx`
   - `web/components/chat/ChatMessage.tsx`
   - The assistant explanation and result card render as one assistant response.
   - Confirmation actions and result actions are structured events, not fake user text.
   - Result cards render before the summary and own the save-strategy control.

## Action Events

Confirmation actions are available only while a strategy is awaiting approval:

- `run_backtest`
- `change_dates`
- `change_asset`
- `adjust_assumptions`
- `cancel_confirmation`

Result actions are available only after a completed run:

- `show_breakdown`
- `refine_strategy`
- `save_strategy`

`save_strategy` belongs inside the result card. It saves from canonical run/result state, not reconstructed frontend prose.

## Persistence Boundary

Supabase-backed persistence owns conversation continuity:

- `conversations` stores the active thread.
- `messages` stores user/assistant text and structured card metadata.
- `backtest_runs` stores immutable config, metrics, result card, chart, and event markers.
- `strategies` stores saved result-backed ideas for the Strategies surface.

Reloading or navigating away from chat must hydrate both visible messages and structured UI artifacts, including confirmation cards, result cards, latest run ids, and available actions. A reload must not turn a structured result into plain text only.

Runtime memory remains checkpoint-first. If a pending confirmation action arrives after reload, the API validates the LangGraph checkpoint before execution. Message metadata may supply a conservative fallback snapshot only when it contains structured confirmation payload; otherwise the assistant asks the user to reconfirm instead of silently running incomplete state. Result follow-ups may recover the latest canonical run reference from message metadata and `backtest_runs`, but Save Strategy must still use a concrete run id from the result card.

Collections remain in the schema but launch UI for collections is feature-gated with `NEXT_PUBLIC_COLLECTIONS_ENABLED=false`.

## Fully Supported

- Basic product and education questions.
- Buy and hold for same-asset supported symbols.
- DCA / recurring accumulation with monthly or weekly cadence.
- Indicator threshold strategies when the indicator registry marks the indicator executable.
- Single-asset-class backtests with up to 5 symbols.
- Equity benchmark default: `SPY`.
- Crypto benchmark default: `BTC`.
- Currency-pair benchmark default: the tested pair.
- Long-only execution.

## Partially Supported

- Compound indicator/price/volume confluence can be drafted and preserved, but execution may require simplification to an executable subset.
- Risk overlays such as stop loss, trailing stop, take profit, and partial/full exits are captured in the strategy object. They are only executable where the engine adapter supports the semantics.
- Strategy comparisons are interpreted conversationally. Execution should run supported strategies separately and explain the comparison from real result payloads.

## Unsupported Handling

When a request is not fully executable, Argus must:

- Acknowledge the understood idea.
- Explain the exact limitation.
- Preserve the user intent in the candidate strategy.
- Offer executable simplifications.
- Keep the same thread active.

Examples:

- Mixed equity and crypto in one run is unsupported. Argus should offer separate runs or an asset-class choice.
- Unverified symbols are unsupported until provider lookup succeeds.
- Unsupported compound logic should be preserved as intent and simplified only with user approval.
- Provider data-window limits, including Kraken's 720-candle OHLC window, must be explained as data availability limits with a concrete shorter range or wider timeframe suggestion.

## Result Experience

Result presentation is a single product moment:

1. Render the result card first.
2. Show a short grounded summary from the same result payload.
3. Offer result actions.

The main card shows only high-signal metrics: total return, final value, max drawdown, and benchmark delta. Win rate appears only when closed trades make it meaningful. Secondary metrics and caveats belong in the breakdown.

The chart is a TradingView Lightweight Charts baseline chart using the aggregate portfolio equity curve. Multi-symbol runs must show the portfolio curve, not a cluttered symbol comparison. Entry and exit markers may be capped for readability. TradingView attribution must remain visible.

## Search And Embeddings

Embeddings are not required for the launch chat/backtest loop. Supabase structured state, run metadata, saved strategy records, provider catalogs, and Postgres text search are enough for Alpha. Add pgvector only when Argus needs semantic recall across large saved-history or strategy corpora.

## Environment

Backend package management uses Poetry.

Frontend package management uses Bun.

Required model and data variables:

- `OPENROUTER_API_KEY`
- `AGENT_MODEL` or `AGENT_FALLBACK_MODEL`
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ARGUS_PERSISTENCE_MODE`
- Supabase variables from `.env.example` when running with Supabase persistence.
