# Argus Conversational Runtime

Status: Active Alpha implementation

Argus now treats conversation as the product surface and backtesting as an execution tool. The active `/api/v1/chat/stream` path runs the LangGraph agent runtime with a model-backed interpretation layer before validation, confirmation, execution, and explanation.

## Runtime Contract

The model proposes meaning. Argus validates it. The user confirms it. The engine executes it.

This separation is intentional:

- LLM interpretation is used for natural language understanding, strategy type inference, structured strategy drafting, ambiguity detection, correction-aware follow-ups, conversational unsupported handling, confirmation wording, and result explanation.
- Deterministic code is used for capability truth, Alpaca asset availability, asset class validation, required-field gating, same-asset restrictions, execution defaults, benchmark selection, backtest execution, result envelopes, and stream event shape.
- The LLM cannot silently mark unsupported behavior as executable, invent asset availability, change symbols, bypass confirmation, or fabricate result metrics.

## Active Layers

1. Conversational intelligence
   - `src/argus/agent_runtime/llm_interpreter.py`
   - Uses OpenRouter through `ChatOpenRouter` with structured output.
   - Preserves raw user phrasing and normalized strategy meaning.

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
   - Alpaca `/v2/assets` is the availability and asset-class source of truth through `resolve_asset`.

5. Execution truth
   - `src/argus/agent_runtime/tools/real_backtest.py`
   - `src/argus/agent_runtime/stages/execute.py`
   - Runs real supported backtests and returns the same result envelope used by the UI.

6. UI integration
   - `web/components/chat/ChatInterface.tsx`
   - `web/components/chat/ChatMessage.tsx`
   - The assistant explanation and result card render as one assistant response.

## Fully Supported

- Basic product and education questions.
- Buy and hold for same-asset supported symbols.
- DCA / recurring accumulation with monthly or weekly cadence.
- Indicator threshold strategies when the execution adapter can map the threshold.
- Single-asset-class backtests with up to 5 symbols.
- Equity benchmark default: `SPY`.
- Crypto benchmark default: `BTC`.
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
- Unverified symbols are unsupported until Alpaca asset lookup succeeds.
- Unsupported compound logic should be preserved as intent and simplified only with user approval.

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

