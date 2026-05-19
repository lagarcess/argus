# Argus Conversational Runtime

Status: Active Alpha implementation

Argus treats conversation as the product surface and backtesting as an execution tool. The active `/api/v1/chat/stream` path runs the LangGraph agent runtime with a model-backed interpretation layer before validation, confirmation, execution, persistence, and explanation.

## Runtime Contract

The model proposes meaning. Argus validates it. The user confirms it. The engine executes it.

## Conversational Artifact Contract

Each active chat turn is grounded in one conversational artifact:

- a pending strategy draft awaiting clarification or confirmation, or
- a completed result awaiting follow-up.

Every user turn must start a draft, patch the pending draft, answer a pending field, ask about the draft, confirm the draft, ask about the latest result, or recover the latest failed turn. Argus should not restart from blank state when a prior artifact clearly exists, and it must not execute a completed draft until the user has seen and approved the confirmation state.

This separation is intentional:

- LLM interpretation is used for natural language understanding, strategy type inference, structured strategy drafting, ambiguity detection, correction-aware follow-ups, conversational unsupported handling, confirmation wording, and result explanation.
- Deterministic code is used for capability truth, provider availability, asset class validation, required-field gating, same-asset restrictions, execution defaults, benchmark selection, indicator execution specs, backtest execution, result envelopes, persistence, and stream event shape.
- The LLM cannot silently mark unsupported behavior as executable, invent asset availability, change symbols, skip required confirmation, or fabricate result metrics.
- Before confirmation, Argus runs semantic conservation checks so explicit user constraints outrank defaults. If a user-supplied date, cadence, asset, or money role cannot be preserved or normalized, Argus clarifies instead of emitting a confident `Ready to run` card.
- For DCA / recurring accumulation, `capital_amount` is the recurring contribution. Current DCA execution supports that one executable dollar amount only. Starting principal, total capital budgets, and contribution ceilings may be acknowledged as user intent, but they are future engine capabilities and must not overwrite the contribution amount.
- Deterministic fallback cannot become the normal assistant voice. If the LLM fails, Argus may preserve truth internally, but user-facing copy must be natural recovery language rather than raw fields, enums, or starter prompts.

### Artifact Metadata Spine

Runtime snapshots and message metadata may carry lightweight artifact references
for the active draft, active confirmation, latest completed result, latest failed
action, and saved strategy state. These references are additive continuity
metadata: they help Argus select and hydrate the visible artifact, but they do
not replace LangGraph runtime memory or Supabase product records.

Result references are derived from immutable `backtest_runs` records. The
runtime may expose a result fact bank containing the run id, conversation id,
strategy id, asset class, symbols, benchmark, metrics, config snapshot, result
card, chart, and trades so follow-up answers can use actual run facts after
reload. Engine metrics and `backtest_runs.config_snapshot` remain the canonical
truth; the fact bank is a transport/context projection.

Failed-action references preserve recoverable action context such as the action
type, launch payload, failure classification, and user-safe error. They exist so
"try again" can bind to the latest failed visible action without restarting the
thread from blank. Deterministic code still validates capability, stale state,
and authorization before any retry executes.

Saved-strategy metadata, including `saved_strategy_id`, is result artifact state.
It makes Save Strategy idempotent and allows reload to show that a result was
already saved. Saving still uses a concrete run id and canonical result state,
not frontend prose or regenerated assistant text.

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

Confirmation cards are durable transcript artifacts, but only the latest active
confirmation is executable. New refinement confirmations supersede older cards,
and a completed result also makes prior confirmation cards historical. The UI may
render superseded cards as muted `Updated` cards, but backend execution still
checks the active confirmation identity before running.

Clarification prompts may persist a single pending resolution candidate, such as
Apple Inc. (`AAPL`) for an ambiguous "Apple" request. If the next user turn is a
short affirmative answer, deterministic guardrails may accept only that stored
candidate for that stored field after LLM interpretation. This keeps ordinary
language LLM-first while preventing repeated binary clarifications.

Collections remain in the schema but launch UI for collections is feature-gated with `NEXT_PUBLIC_COLLECTIONS_ENABLED=false`.

## Fully Supported

- Basic product and education questions.
- Buy and hold for same-asset supported symbols.
- DCA / recurring accumulation with monthly or weekly cadence and one recurring contribution amount.
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
- DCA requests that include separate starting principal, total capital budget, or investment ceiling are understood conversationally, but those modifiers are not executable in the current DCA engine. Argus should offer a recurring-only run, an adjusted recurring contribution, or a buy-and-hold style test using starting capital.

TODO(dca-engine): Add first-class support for DCA starting principal, investment ceilings, and recurring contribution combinations across engine config, launch request models, LangGraph semantic contracts, confirmation cards, result assumptions, and model capability wording.

## Unsupported Handling

When a request is not fully executable, Argus must:

- Acknowledge the understood idea.
- Explain the exact limitation.
- Preserve the user intent in the candidate strategy.
- Offer executable simplifications.
- Keep the same thread active.

Examples:

- Mixed equity, crypto, and currency pairs in one run are unsupported. Argus should offer separate runs or an asset-class choice.
- Unverified symbols are unsupported until provider lookup succeeds.
- Unsupported compound logic should be preserved as intent and simplified only with user approval.
- Provider data-window limits, including Kraken's 720-candle OHLC window, must be explained as data availability limits with a concrete shorter range or wider timeframe suggestion.

## Result Experience

Result presentation is a single product moment:

1. Render the result card first.
2. Show a short grounded summary from canonical run/result context, not stale
   original user wording.
3. Offer result actions.

The main card shows only high-signal metrics: total return, final value, max drawdown, and benchmark delta. Win rate appears only when closed trades make it meaningful. Secondary metrics and caveats belong in the breakdown.

`Show breakdown` is an educational follow-up, not a second source of result
truth. The preferred path is an LLM-authored markdown explanation that can vary
its headings and framing so the conversation does not feel templated. The
backend derives an internal fact bank from the stored run/result context, asks
the LLM to structure sections with fact references, then renders those facts
deterministically. If the generated breakdown is malformed or references facts
outside that bank, Argus should fall back to the deterministic grounded
breakdown.

Breakdown suggestions must respect capability truth. The assistant may suggest
tests that are runnable now, ideas it can help draft, or future engine
capabilities, but it must not imply unsupported strategies are executable today.
Structured breakdown actions should emit an `explain` stage before final text so
the UI can show a clear working state while preserving canonical SSE frame
types.

The chart is a TradingView Lightweight Charts baseline chart using the aggregate portfolio equity curve. Multi-symbol runs must show the portfolio curve, not a cluttered symbol comparison. Entry and exit markers may be capped for readability. TradingView attribution must remain visible.

## Search And Embeddings

Embeddings are not required for the launch chat/backtest loop. Supabase structured state, run metadata, saved strategy records, provider catalogs, and Postgres text search are enough for Alpha. Add pgvector only when Argus needs semantic recall across large saved-history or strategy corpora.

## Environment

Backend package management uses Poetry.

Frontend package management uses Bun.

Required model and data variables:

- `OPENROUTER_API_KEY`
- `AGENT_MODEL`: primary low-cost conversational model for normal chat,
  clarification, education, and flexible prose.
- `AGENT_STRUCTURED_MODEL`: optional model for durable JSON-schema artifact
  interpretation. Leave unset in low-cost development mode unless live QA proves
  the primary/fallback pair cannot produce complete artifacts.
- `AGENT_FALLBACK_MODEL`: secondary model tried when the primary configured
  model fails, times out, or returns a structurally valid but incomplete
  artifact.
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ARGUS_PERSISTENCE_MODE`
- Supabase variables from `.env.example` when running with Supabase persistence.

Structured artifact calls use OpenRouter JSON-schema responses directly and
disable reasoning with `reasoning: {"effort": "none"}`. The reason is practical:
for artifact extraction Argus needs complete JSON content, not billable hidden
reasoning tokens. If a provider rejects that reasoning setting, the client may
retry the same request without it before moving to the next configured model.

## Conversational Runtime Decision Filter

When changing conversational runtime behavior, ask:

> *Does this keep the conversation resilient under messy human curiosity while preserving deterministic validation, artifacts, and recovery?*

If no, it likely should wait or be redesigned.
