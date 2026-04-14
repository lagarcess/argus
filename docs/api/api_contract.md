# API Contract – Argus Observatory (v1.0.0)

**Status**: Locked (Source of Truth)
**Version**: 1.0.0
**Last Updated**: 2026-04-10
**Base URL**: `https://api.argus.app/api/v1/`
**OpenAPI Spec**: [openapi.yaml](openapi.yaml)

---

## 1. Overview & Scope
- **Purpose**: Argus is a mobile-first PWA for high-fidelity retail trading backtesting. It closes the "Reality Gap" by providing high-performance simulations that account for slippage, fees, multi-symbol iteration, and Walk-Forward Analysis (WFA).
- **In Scope (MVP North Star)**: Historical backtesting (Equities, Crypto, Options, Forex), Agentic Strategy Drafting (NL2D), Agentic Journaling (Memos API), Social Sharing (OpenGraph), Discovery Screeners, Portfolio-Level Testing, Monetization (Lemon Squeezy), and early TradingView Charting Datafeeds.
- **Architectural Philosophy: Signal-First Execution**: Unlike generic retail tools, Argus prioritizes **Pure Signal Fidelity**. Risk parameters (Stop Loss/Take Profit) are currently reserved in the schema (`null` by default) to encourage traders to build high-fidelity exit signals (e.g., indicator-based stops) before relying on fixed-percentage risk logic.
- **Out of Scope (V1.x Future Bets)**: Real-time competitive battles (Training Ground), Broker configuration exports (MT5, TradeStation).

---

## 2. Current System vs. API Contract (Gap Analysis)
This section aligns the aspirational Master Contract against our *current* codebase to establish the exact development gaps required for MVP parity. Checkmarks denote systems kept "as-is", while empty boxes represent the architectural gaps to build.

**What We Have (Supported & Parity Achieved)**:
- [x] **High-Speed Execution Core**: `src/argus/engine.py` + `analysis/patterns.py`, `harmonics.py`, `structural.py`, `indicators.py` successfully use Numba JIT + VectorBT for single-symbol pattern/harmonic confluence and simulation. This rigorously meets the `<3s` SLA on daily data.
- [x] **Hybrid Caching Router**: `market/data_provider.py` + Alpaca fetcher with TTL disk cache blocks UI latency.
- [x] **Strict RLS Security**: Supabase JWT `httpOnly` sessions are accurately mapped to Row-Level Security ensuring `auth.uid()` matches.
- [x] **Engine: Portfolio-Level Processing**: Engine core and API fully support multi-symbol `symbols: string[]` via vectorized VectorBT Portfolio paths.
- [x] **Strategy Persistence (CRUD)**: `GET/POST/PUT/DELETE /strategies` fully implemented with PersistenceService sync.
- [x] **Simulation History / Listing**: `/api/v1/history` supports cursor-based pagination and summary retrieval.
- [x] **Institutional Execution Model**: High-fidelity 2-pass simulation (Ideal vs. Realistic) implemented. Engine decomposes total drag into priority-scaled slippage, fees, and volatility hazards as required by the institutional schema.

**What We Lack (Critical Gaps to Build for Ecosystem Loop)**:
- [ ] **Hybrid Resource-Aware Quotas**: Evolving from simple "one-way" counts to an execution-weighted model (Pro) and concurrency-slot model (Max) to handle high-complexity portfolio simulations.
- [ ] **Engine: Walk-Forward Analysis (WFA)**: Missing orchestration layer for train/test splitting and parameter optimization.
- [ ] **AI: Collaborative Drafting Engine**: Integration of liteLLM/OpenRouter for NL-to-Strategy conversion and "Psychological Mirroring" (connecting Memos to user bias).
- [ ] **Persistence: usememos Integration**: Bridging the journaling layer with the simulation history for a complete trader's loop.
- [ ] **Datafeed Compliance**: `/market/bars` must implement full TradingView UDF (gated by `advanced_charting`).
- [ ] **Quota Reset Mechanics**: `reset_monthly_quotas` function exists but missing Supabase Edge Function cron job/trigger.
- [ ] **Agentic AI Drafting (`POST /agent/draft`)**: Missing LangChain endpoint returning unexecuted `StrategySchema` drafts.
- [ ] **Social Sharing & Storage (`POST /share`)**: Implementing Lightweight Text Card MVP.
- [ ] **Monetization Architecture**: Missing protected `/billing/checkout` endpoint and Supabase Edge Function webhook (`/webhook/billing`).
- [ ] **Agentic Journaling Auth**: Missing `USEMEMOS_API_KEY` configuration and secure background push logic.
- [ ] **Discovery Screeners**: Lacks `/screeners` proxy to Alpaca Movers / Most-Actives.
- [ ] **User Feedback Portal (`POST /feedback`)**: Missing Discord webhook endpoint.

---

## 3. Architecture & Technical Stack (MVP for Speed)
- **Frontend**: TypeScript + Next.js 15 (Bun).
- **Backend API**: Python FastAPI (Poetry).
- **Backend Quantitative Core**: **VectorBT + Numba**.
  - **Architectural Directive for Engine Gaps**: Keep all existing `@njit` numerical logic untouched! It is highly optimized and works beautifully.
  - **The Fix**: Add a thin `BacktestConfig` modular wrapper around `engine.py`. This wrapper will loop/vectorize the `symbols: string[]` array, instantiate the native VectorBT portfolio functions, enable WFA chunks, and inject the configurable reality gap parameters (slippage/fees) *before* passing the vectors to the immutable Numba layer.

---

## 4. Monetization & Entitlement (The "Premium Hook")
We expose high-value AI features broadly to capture market share but cap daily volumes aggressively to hook users into paying for pipeline velocity.

| Feature          | **Free for Everyone** | **Plus (Active)**   | **Pro (Advanced)**      | **Max (P99 Power)**  |
| :--------------- | :-------------------- | :------------------ | :---------------------- | :------------------- |
| **Quota**        | 10 execs / day        | 500 / month         | Unlimited               | Unlimited (Clustered)|
| **Portfolio**    | Single Symbol         | Multi-Symbol (5)    | Multi-Symbol (15)       | Multi-Symbol (100)   |
| **History [D]**  | 1yr (D) / 3d (I)      | 3yr (D) / 7d (I)     | 5yr (D) / 14d (I)       | 7yr+ (D) / 30d (I)   |
| **Charting**     | TV (Interactive)      | TV + Persistence    | TV + Execution Mapping  | TV + Alpha Overlays  |
| **Assets [A]**   | Equities/Crypto       | + Forex             | + Options (Greeks)      | + Multi-Leg Spreads  |
| **Reality Gap**  | Basic (Impact %)      | Basic               | **Detailed Attribution**| **Detailed Attribution**|
| **Execution**    | Retail (Fixed Drag)   | Retail               | **Institutional Model** | **Institutional Model**|
| **Journaling**   | Standalone Memos      | + Rich Media / Tags  | **Contextual Linking**  | **Agentic Psychology**  |
| **AI Agent**     | UI Insights (Limited) | UI Insights (Volume) | **Strategy Co-Drafter** | **Behavioral Mirror**   |

> [!NOTE]
> **[D] History Lookback**: (D) indicates Daily resolution; (I) indicates Intraday frequencies (15m, 1h).
> **[A] Asset Constraints**: 5+ years historical lookback for some assets due to provider liquidity data parity.

### 4.A Psychographic Persona Mapping
Each tier is engineered to satisfy the specific risk psychology and architectural needs of our target users.

| Tier      | **Persona** | **Psychographic Driver**      | **Core Need Met**                |
| :-------- | :---------- | :---------------------------- | :------------------------------- |
| **Free**  | **Explorer**| "Can I find alpha?"           | Low-friction testing & validation|
| **Plus**  | **Enthusiast**| "Is my system stable?"        | Breadth of symbols & persistence |
| **Pro**   | **Quant**| "Will this fill in reality?"  | Institutional physics & fidelity |
| **Max**  | **Portfolio Manager**| "Can I scale this infinitely?"| Unlimited throughput & refit loops|

### 4.B Resource-Aware Quota Architecture (Roadmap)
To balance server stability with institutional power, Argus is transitioning from simple "Backtest Counts" to a hybrid resource-aware model.

#### The Three Models
1.  **The Bucket Model (Free/Plus)**: Standard consumable count (e.g., 500/mo). Simple, predictable, and fair for "Explorer" work.
2.  **The Weighted Model (Pro)**: Complexity-weighted credits where `Cost = symbols * years`. This prevents "Quants" from overloading the engine while letting them run thousands of simple tests.
3.  **The Slot Model (Max)**: Unlimited total volume but restricted **Concurrency Slots** (e.g., 5 parallel sims). This guarantees "Portfolio Managers" 24/7 throughput while capping peak server load (SOTA industry standard).

#### Strategic Reasoning
- **Efficiency**: Protects the engine from "Complexity DDoS" (e.g., thousands of parallel 100-symbol resets).
- **Fairness**: Users pay for the value they extract. A massive broad-market scan correctly costs more than a single-stock experiment.
- **Perception**: "Portfolio Managers" prioritize **Throughput over Totals**. A slot-based model feels more like a professional workstation.

> [!IMPORTANT]
> **Current State**: All tiers currently use the **Bucket Model** (1 simulation = 1 credit). Transition to Weighted/Slot logic is scheduled for future release.

### 4.C Feature Definition Glossary
Simple, relevant definitions to clarify the user experience at each mastery level.

| Feature Area | **Explorer / Enthusiast (Retail)** | **Quant / Portfolio Manager (Institutional)** |
| :--- | :--- | :--- |
| **Charting** | **Standard**: Interactive TV candles. | **Institutional**: Logic-mapping (Executions/Overlays). |
| **Reality Gap** | Basic "Impact %" — one total drag score. | **Detailed Attribution**: Fees vs. Slippage vs. Vol. |
| **Execution** | **Retail Model**: Fixed-bps/tick slippage. | **Institutional Model**: Liquidity-aware physics. |
| **Journaling** | **Memos**: Professional standalone notes. | **Deep Integration**: Asset-linked logs + AI Bias analysis. |
| **AI Agent** (liteLLM) | **UI Insights**: Analysis hook (Tiers 1-2). | **Collaborative**: NL-to-Draft & Behavioral Insight (Tiers 3-4). |

---

## 5. General Conventions & Error Handling
- **Pagination**: **100% Cursor-based** (opaque base64 `timestamp+id`). Required for `/history` and `/strategies`.
- **Admin Bypass**: The `is_admin = true` profile flag supersedes all backend quota limits and rate limits.
- **Rate Limiting**: Every response returns headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`.
- **Error Responses**: Follow RFC 9457 Problem Details. Disabled features return 403, Quota exhaustions return 402.

**Feature Flag Object** (In `UserResponse` session):
```json
{ "advanced_charting": false, "options_enabled": false, "memos_sync": true }
```

---

## 6. Exhaustive Endpoint & Schema Blueprints

### A. Core Engine (`/backtests` & `/history`)
- **POST /api/v1/backtests**: Atomic execution. Automatically fires Supabase RPC `decrement_user_quota()`.

  **Request Schema**:
  ```json
  {
    "strategy_id": "uuid-v4",
    "symbols": ["AAPL", "MSFT"] // Overrides saved strategy symbols if provided
  }
  // OR INLINE
  {
    "symbols": ["AAPL"],
    "timeframe": "15m",
    "slippage": 0.001,
    "fees": 0.005,
    "participation_rate": 0.1,    // [PRO] 0.001 to 1.0 (Liquidity Gating)
    "execution_priority": 1.0,   // [PRO] 0.0 (Maker) to 1.0 (Taker)
    "va_sensitivity": 1.0,       // [PRO] Volatility sensitivity scaling
    "slippage_model": "vol_adjusted", // [PRO] "fixed" | "vol_adjusted"
    "entry_criteria": [{"indicator": "RSI", "operator": "<", "value": 30}],
    "exit_criteria": [{"indicator": "EMA", "operator": "cross_below", "indicator_b": "Price"}],
    "stop_loss_pct": null,    // [FUTURE] Reserved for fixed percentage-based risk
    "take_profit_pct": null   // [FUTURE] Reserved for fixed percentage-based risk
  }
  ```
  **Response Schema** (`BacktestResponse`):
  ```json
  {
    "id": "uuid-v4",
    "config_snapshot": { "timeframe": "15m", "symbols": ["AAPL"] },
    "summary": { // Renders UI top-level cards & history tabular views
      "total_return_pct": 14.5,
      "win_rate": 0.62,
      "sharpe_ratio": 1.8,
      "max_drawdown_pct": -0.05
    },
    "reality_gap_metrics": {
      "slippage_impact_pct": 1.2,
      "fee_impact_pct": 0.4,
      "vol_hazard_pct": 0.8,      // Cost of volatility/liquidity drag
      "fidelity_score": 94.5      // Aggregated confidence/realism score
    },
    "full_result": { // Separated to prevent enormous bloated tables unless queried
      "equity_curve": [100, 101.5, 99.8],
      "trades": [{"entry_time": "...", "entry_price": 405.10, "exit_price": 410.20, "pnl_pct": 1.2}],
      "pattern_breakdown": { "doji": 4, "engulfing": 2 }
    }
  }
  ```

### B. Agentic Intelligence & Strategies (`/agent/draft` & `/strategies`)
- **POST /api/v1/agent/draft**: Returns an *unexecuted* `StrategySchema` requiring user confirmation.
- **CRUD**: `GET/POST/PUT/DELETE /api/v1/strategies`.

### C. Data Proxy & Charting (`/market/bars`)
- **GET /api/v1/market/bars**: TradingView UDF (Universal Datafeed) compliance handler.
  - **Query Params**: `symbol`, `from`, `to`, `resolution`.
  - **Response (UDF)**: `{"t": [...], "o": [...], "h": [...], "l": [...], "c": [...], "v": [...], "s": "ok"}`
- **GET /api/v1/screeners**: Discovery proxy mapping to Alpaca Movers / Most-Actives.

### D. Sharing & Monetization (`/share` & `/webhook/billing`)
- **POST /api/v1/share**: Takes a `simulation_id`. Renders image, stores in Supabase public `/graphs` bucket.
  ```json
  {
    "vanity_url": "https://argus.app/s/abX9k",
    "og_image": "https://[project-id].supabase.co/.../abX9k.png"
  }
  ```
- **POST /webhook/billing**: Supabase Edge Function processing gateway hooks to bump tiers.

---

## 7. Database Schema & RLS
- **`profiles`**, **`strategies`**, **`simulations`**, **`user_feedback`**.

### Supabase Migrations & RPCs
- **Quota Decrement**: `supabase/migrations/xxxx_add_rpc.sql`
  ```sql
  CREATE OR REPLACE FUNCTION decrement_user_quota(user_uuid UUID)
  RETURNS void LANGUAGE plpgsql SECURITY DEFINER AS $$
  BEGIN
    UPDATE profiles SET remaining_quota = remaining_quota - 1
    WHERE id = user_uuid AND remaining_quota > 0 AND is_admin = false;
  END;
  $$;
  ```
- **CRON Quota Reset**: `supabase/migrations/yyyy_add_cron.sql`. Maps `pg_cron` to reset limits based on `profiles.subscription_tier`.

---

## 8. Implementation Dependency Order
1. **Schema & Mocks**: Generate `openapi.yaml` from this contract for frontend unblocking.
2. **Supabase Migrations**: Run SQL for tables, RPCs, and Cron resets.
3. **Quantitative Engine Wrapper**: Add the `BacktestConfig` wrapper in `engine.py` (implementing multi-symbol + WFA + native VectorBT slippage arrays). Keep `@njit` logic untouched.
4. **Core CRUD API**: Build `GET/POST /strategies` and `GET /history`.
5. **Execution API**: Route `/backtests` to the updated Wrapped Engine.
6. **Agentic Layer**: Tie LangChain to `/agent/draft`.
7. **Ecosystem Polish**: OpenGraph `/share`, TradingView `/market/bars`, and Monetization Webhooks.
