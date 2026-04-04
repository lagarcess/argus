# Analytics Data Backend: Requirements & Gap Analysis
**Author**: Principal Data Engineer
**Project**: Crypto Sentinel

As the Principal Data Engineer, I have conducted a deep dive into `main.py` execution orchestrations and `domain/schemas.py` Data Contracts. The overall intent of the system is a high-fidelity algorithmic trading and backtesting engine. However, the current analytical backend contains implementation disconnects that break this intent.

Below is the refactored gap analysis outlining the exact problems, proposed solutions, benefits, and trade-offs. These findings underscore the need for a targeted migration away from legacy, anti-pattern pipelines toward a unified, natively analytical system.

---

## 1. The Current Architecture: How It Works Today

The existing Crypto Sentinel analytics backend is characterized by fragmented data silos, heavy reliance on persistent staging tables, and Python-driven analytical rollups. Below is a detailed mapping of the current operational flow:

### 1. Data Generation (The Hot Path)
- **Signal Generation (`signal_generator.py`)**: Continuously analyzes market data (candles, volume) to detect geometric patterns and technical confluence (RSI, ADX). It generates a rich `Signal` Pydantic model.
	- If a signal passes safety/quality gates, it is saved to the Firestore `live_signals` collection.
	- If a signal fails a quality gate (e.g., poor volume), an identical "shadow" signal is generated and saved directly to the Firestore `rejected_signals` collection.
- **Trade Execution (`execution.py`)**: When a valid `live_signal` is executed via Alpaca, a `Position` model is generated and saved to the Firestore `live_positions` collection.

### 2. Archival Pipelines (The Move to Cold Storage)
Every night (`T-0`), Jenkins/Cloud Run executes a suite of Python pipelines to extract data from the Firestore hot storage and insert it into BigQuery:
- **`trade_archival.py`**: Queries Firestore for `CLOSED` records in `live_positions`. It extracts these into a Pydantic `TradeExecution` schema. *Crucially, it does not fetch the parent `live_signal`.* The `live_signal` remains in Firestore until a 30-day GCP TTL deletes it. The pipeline truncates `stg_trades_import`, inserts the records, and issues a `MERGE` SQL statement into the persistent `fact_trades` table.
- **`rejected_signal_archival.py`**: Queries Firestore for records in `rejected_signals`, loads them into `stg_rejected_signals`, and issues a `MERGE` into `fact_rejected_signals`.
- **`expired_signal_archival.py`**: Queries `live_signals` directly for records marked `EXPIRED`, loads them into `stg_signals_expired_import`, and issues a `MERGE` into `fact_signals_expired`.
- **Unaccounted State**: Signals marked as `INVALIDATED` currently have no archival pipeline and are silently deleted by TTL.

### 3. Financial Reconciliation (Asynchronous Patching)
Because broker fees and final fill prices are often asynchronous:
- **`fee_patch.py`**: Queries the Alpaca API for actual realized fees (CFEE) on trades closed > 24 hours ago. It runs an `UPDATE` statement directly against BigQuery's `fact_trades` to replace estimated fees.
- **`price_patch.py`**: Heals missing exit prices directly via SQL `UPDATE` against `fact_trades`.

### 4. Analytical Rollups (The Anti-Pattern Loop)
- **`agg_strategy_daily.py`**: Connects to BigQuery, runs a `GROUP BY` query on `fact_trades` to summarize daily performance, pulls the result out into Python memory, pushes it to `stg_agg_strategy_daily`, and issues a `MERGE` into `agg_strategy_daily`.
- **`performance.py`**: Reads `agg_strategy_daily` into Python, calculates win rates and portfolio drawdowns, and pushes the final dataframe to `stg_performance_import` before merging into `summary_strategy_performance`.

**Current System Summary**: The system relies heavily on Python to orchestrate SQL operations and maintain ~26 physical tables (including test environments). Furthermore, the complete separation of `fact_trades`, `fact_rejected_signals`, and `fact_signals_expired` necessitates extremely complex, multi-table `UNION` queries for analysts attempting robust backtesting. The most devastating flaw is that `trade_archival.py` drops the ML metadata from winning trades.

---

## 2. The Lean Architecture Vision

The proposed Lean Architecture radically simplifies the GCP footprint by leaning aggressively into Native BigQuery operations, eliminating redundant staging tables, and consolidating the data structures to support accurate quantitative backtesting.

### 1. Unified Theoretical Backtesting Storage
Instead of sharding signals into four tables (`rejected`, `expired`, `executed`, `invalidated`), the Lean Architecture mandates two primary Fact tables:
- **`fact_trades`**: The immutable financial ledger. Strictly adhering to the `TradeExecution` Pydantic model (PnL, Fees, Alpaca Order IDs, Slippage). It does not contain strategy indicators.
- **`fact_theoretical_signals`**: The backtesting super-table. This table captures the complete `Signal` Pydantic structure natively generated by `signal_generator.py`, including the `confluence_snapshot` (RSI, ADX, SMA flags, Volume metrics) and harmonic structural arrays.
	- Every `REJECTED`, `EXPIRED`, `INVALIDATED`, and **`EXECUTED/CLOSED`** signal will be archived here.
	- This creates a massive, singular dataset for analysts to query true market history without survivorship bias or multi-table `UNION` joins. Reconciling financial performance with technical indicators is a simple `JOIN` between `fact_trades.trade_id` and `fact_theoretical_signals.signal_id`.

	**Consolidated Field List** (Pydantic: `FactTheoreticalSignal`, Issue #360):

	| Section | Field | Type | Required | Notes |
	|---|---|---|---|---|
	| Core Identity | `doc_id` | `str` | No | Firestore document ID |
	| | `ds` | `date` | **Yes** | Partition key |
	| | `signal_id` | `str` | **Yes** | Deterministic UUID5 |
	| | `strategy_id` | `str` | **Yes** | FK to dim_strategies |
	| | `symbol` | `str` | **Yes** | e.g., `BTC/USD` |
	| | `asset_class` | `AssetClass` | **Yes** | CRYPTO / EQUITY |
	| | `side` | `OrderSide` | **Yes** | BUY / SELL |
	| Outcome | `status` | `SignalStatus` | **Yes** | EXPIRED, REJECTED_BY_FILTER, etc. |
	| | `trade_type` | `str` | **Yes** | EXECUTED, FILTERED, THEORETICAL, RISK_BLOCKED |
	| | `exit_reason` | `ExitReason` | No | TP1, STOP_LOSS, etc. |
	| | `rejection_reason` | `str` | No | Quality gate failure description |
	| Signal Params | `entry_price` | `float` | **Yes** | Target entry price |
	| | `pattern_name` | `str` | **Yes** | e.g., `bullish_engulfing` |
	| | `suggested_stop` | `float` | **Yes** | Stop-loss price |
	| | `take_profit_1/2/3` | `float` | No | Profit targets |
	| | `valid_until` | `datetime` | **Yes** | Signal expiration |
	| | `created_at` | `datetime` | **Yes** | Signal creation time |
	| Structural | `pattern_classification` | `str` | No | STANDARD / MACRO |
	| | `pattern_duration_days` | `int` | No | First pivot → signal |
	| | `pattern_span_days` | `int` | No | First → last pivot |
	| | `conviction_tier` | `str` | No | HIGH / STANDARD |
	| | `structural_context` | `str` | No | Harmonic regime |
	| Nested (ADR #359) | `confluence_factors` | `List[str]` | No (default `[]`) | Triggers list |
	| | `confluence_snapshot` | `STRING` (JSON) | No | Indicator values |
	| | `harmonic_metadata` | `STRING` (JSON) | No | Fibonacci ratios |
	| | `rejection_metadata` | `STRING` (JSON) | No | Forensic audit data |
	| | `structural_anchors` | `REPEATED RECORD` | No | Pivot geometry |
	| Theoretical P&L | `theoretical_exit_price` | `float` | No | Simulated exit |
	| | `theoretical_exit_reason` | `str` | No | Simulated exit reason |
	| | `theoretical_exit_time` | `datetime` | No | Simulated exit time |
	| | `theoretical_pnl_usd` | `float` | No | Simulated P&L ($) |
	| | `theoretical_pnl_pct` | `float` | No | Simulated P&L (%) |
	| | `theoretical_fees_usd` | `float` | No | Simulated fees |
	| Near-Miss | `distance_to_trigger_pct` | `float` | No | Entry proximity |
	| FK | `linked_trade_id` | `str` | No | FK to fact_trades (EXECUTED only) |

### 2. Radical Virtualization (Temp Tables)
We will eradicate the 14+ persistent `stg_` tables currently cluttering BigQuery.
- The base `BigQueryPipelineBase` Python framework will be refactored. Instead of using `client.load_table_from_json()` targeting a persistent `dataset.stg_table`, the pipeline will build a `CREATE TEMP TABLE stg_temp AS ...` SQL injection payload dynamically.
- The Python runner holds the batch JSON strictly in memory (costing ~1MB for 1,000 signals, which is 0.2% of a standard Cloud Run instance limit).
- The pipeline executes the TEMP TABLE creation and the production `MERGE` inside a single Python/BigQuery session context. When the pipeline disconnects, BigQuery automatically drops the RAM-based temporary table. The tables physically disappear to the outside observer, ensuring perfect hygiene.

### 3. Strategy Configuration Linking (SCD Enforcement)
- `dim_strategies` is synced from Firestore to BigQuery exactly as it is today.
- However, the `SignalGenerator` in Python will dynamically pull active IDs from `dim_strategies`. Currently, trades are associated with a hardcoded `pattern_name` (e.g. "bullish_engulfing"). Going forward, they will be associated with the UUID `strategy_id` defined by the Operations team in Firestore. This guarantees that BigQuery relationships never fall back to `"UNKNOWN"`.

### 4. Pure SQL Native Rollups
We will delete the `agg_strategy_daily.py` and `performance.py` Python pipelines completely from the `crypto-signals` repository.
- Analytics generation belongs in the data warehouse. We will create two Native BigQuery objects:
	- `CREATE VIEW agg_strategy_daily AS ( ... )`
	- `CREATE MATERIALIZED VIEW summary_strategy_performance AS ( ... )`
- These views natively read straight from `fact_trades` and `dim_strategies`. They update instantaneously without consuming Python compute overhead, zeroing out external failure domains and data "round-tripping" latency.

**Lean Vision Summary**: The Cloud Run backend only handles the physical bridge from Hot Firestore -> Cold BigQuery. Once inside BQ, all transformations and aggregations occur natively. Staging tables are vaporized into BQ-managed Temp logic, and backtesting algorithms query exactly one table (`fact_theoretical_signals`) to understand the entirety of the quantitative landscape.

---

## 3. High-Level Data Ecosystem & Schema Mapping

To understand the scope of the required changes, it's essential to map the current physical footprint in BigQuery against the proposed Lean Architecture.

### The Current Ecosystem (26+ Tables)
The current architecture relies on a "Typed Landing Zone" pattern. Every pipeline creates a Staging table (for `MERGE` operations). Because every environment also generates a `_test` table, the footprint is artificially multiplied.

| Pipeline / Module | Staging Table (Landing Zone) | Status | Fact / Target Table (Persistent) | Status |
| :--- | :--- | :--- | :--- | :--- |
| **trade_archival.py** | `stg_trades_import` | **Stale/Empty** (Truncated every run) | `fact_trades` | **Active** (Stores completed executions & PnL) |
| **rejected_signal_archival.py** | `stg_rejected_signals` | **Stale/Empty** | `fact_rejected_signals` | **Active** (Stores signals rejected by risk gates) |
| **expired_signal_archival.py** | `stg_signals_expired_import` | **Stale/Empty** | `fact_signals_expired` | **Active** (Stores signals that expired) |
| **strategy_sync.py** | `stg_strategies_import` | **Stale/Empty** | `dim_strategies` | **Active** (Stores SCD Type 2 config versions) |
| **account_snapshot.py** | `stg_accounts_import` | **Stale/Empty** | `snapshot_accounts` | **Active** (Daily account equity & margin) |
| **agg_strategy_daily.py** | `stg_agg_strategy_daily` | **Stale/Empty** | `agg_strategy_daily` | **Active** (Rollup from `fact_trades`) |
| **performance.py** | `stg_performance_import` | **Stale/Empty** | `summary_strategy_performance` | **Active** (Rollup from `agg_strategy_daily`) |
| *(Missing Pipeline)* | *`stg_signals_invalidated`* | *Missing* | *`fact_signals_invalidated`* | *Missing* (Data is lost) |

*Note: Every table also has a corresponding `_test` counterpart (e.g., `fact_trades_test`), doubling the physical footprint.*

### The Proposed Lean Ecosystem (8 Tables)
The Lean Architecture vaporizes the staging layer into virtual RAM-based Temp Tables and consolidates backtesting structures.

| Proposed Table | Component Type | Purpose & Architecture Change |
| :--- | :--- | :--- |
| **`fact_trades`** | Persistent Table | Standardized financial execution ledger. Strict Pydantic tracking. |
| **`fact_theoretical_signals`** | **[NEW]** Persistent Table | Unified backtesting super-table replacing `fact_rejected`, `fact_expired`, and capturing the missing `invalidated` signals *plus* the ML metadata of executed trades. |
| **`dim_strategies`** | Persistent Table | Continues acting as the SCD Type 2 dimension for risk configurations. |
| **`snapshot_accounts`** | Persistent Table | Continues tracking daily equity. |
| **`agg_strategy_daily`** | **[NEW]** Native BQ View | Replaces the Python pipeline with a 100% native SQL Materialized View. |
| **`summary_strategy_performance`** | **[NEW]** Native BQ View | Replaces the Python pipeline with a native BQ view built on `agg_strategy_daily`. |

**What the Lean Architecture Provides:**
- **Zero Staging Clutter**: Stale and empty `stg_*` tables are replaced by dynamic BigQuery temporary tables (`CREATE TEMP TABLE ...`) that auto-delete at the end of the Python session.
- **Unified Quantitative Sandbox**: Analysts no longer have to `UNION ALL` across multiple fragmented fact tables. All signals (Executed, Rejected, Expired, Invalidated) live in `fact_theoretical_signals`.
- **Zero Python Compute for Rollups**: Shifting from Python batch jobs to Native BQ Materialized Views completely removes data "round-tripping" latency.

---

## 4. Gap Analysis: The Implementation Disconnects

### 4.1. The ML Indicator Data Loss (Survivorship Bias)
**Current Problem:**
When a signal is generated, `engine/signal_generator.py` captures a rich `confluence_snapshot` (RSI, ADX, Volume thresholds). However, if the signal executes successfully, it becomes a `Position`. The `TradeArchivalPipeline` only extracts the `TradeExecution` Pydantic schema (lines 720-745 in `schemas.py`), which completely drops `pattern_name`, `confluence_factors`, and `pattern_classification`. The original `live_signals` record sits in Firestore until the 30-day TTL blindly deletes it. Consequently, the backtesting engine loses the machine learning indicators for all winning/executed trades.

**Proposed Solution:**
Modify the architecture to create a unified `fact_theoretical_signals` table that securely archives the complete `Signal` Pydantic model (including `confluence_snapshot` and structure) *before* or *during* execution. The `fact_trades` table should strictly remain an execution ledger that JOINs back to `fact_theoretical_signals` using `signal_id`.

**Why:**
A quantitative backtesting algorithm cannot tune indicators if it only possesses data on failed (rejected/expired) signals.

**Benefits:**
- Eliminates survivorship bias in the backtest dataset.
- Enables precise hyper-parameter tuning of ML indicators based on actual market wins without bloating the financial `fact_trades` ledger.

**Trade-offs:**
- Requires establishing robust analytical JOIN views to combine signal context with execution reality.

---

## 4.2. The `dim_strategies` Disconnect (Foreign Key Failure)
**Current Problem:**
`strategy_sync.py` cleanly syncs Firestore configs to BQ `dim_strategies` using a Slowly Changing Dimension (SCD Type 2) model with explicit UUIDs. However, `engine/parameters.py` (line 125) hardcodes `strategy_id = pattern_name` (e.g., `"bullish_engulfing"`). If a new custom strategy is configured in Firestore, the generator fundamentally ignores its ID. The BQ Analytical views trying to JOIN `fact_trades.strategy_id` to `dim_strategies.strategy_id` will inevitably fail or fall back to `"UNKNOWN"`.

**Proposed Solution:**
The `SignalGenerator` must dynamically load active configurations from `dim_strategies` and inject the actual `config.strategy_id` into the `Signal` Pydantic model at creation time.

**Why:**
To enforce a strict Data Contract and ensure historical trades can be traced back to the exact risk configuration active at that time.

**Benefits:**
- Guarantees 100% relational integrity in BigQuery.
- Enables A/B testing multiple configurations of the *same* geometric pattern simultaneously.

**Trade-offs:**
- Requires passing state/config into the `SignalGenerator` via dependency injection, slightly increasing network/memory footprints during generation.

---

## 4.3. Staging Table Bloat vs. In-Memory Limits
**Current Problem:**
The pipeline framework uses a "Typed Landing Zone" (persistent `stg_*` tables) for idempotent `MERGE` upserts into Fact tables. This inflates the GCP footprint to 26+ tables and creates "always empty" tables that confuse Operators.

**Proposed Solution:**
Refactor the Python BigQuery pipeline base to use Native BigQuery Temporary Tables. The Cloud Run footprint for executing this is mathematically negligible (~1MB in RAM for 1,000 JSON signal objects). The pipeline pushes JSON strictly to an in-memory Temp Table, runs the `MERGE`, and safely auto-drops the Temp Table upon disconnection.

**Why:**
Optimizes system for GCP's free tier by removing 14+ unnecessary physical tables without sacrificing idempotency.

**Benefits:**
- Massive reduction in infrastructure storage costs and visual clutter.
- Drastically simplifies Terraform and infrastructure-as-code deployments.

**Trade-offs:**
- Removes the ability to manually inspect staging data post-failure (though robust Cloud Logging resolves this observability loss).

---

## 4.4. Signal Fragmentation (The Non-Executed Data Gap)
**Current Problem:**
Non-executed signals are sharded across multiple pipelines: `RejectedSignalArchival`, `ExpiredSignalArchival`, and completely missing logic for `INVALIDATED` states. Querying the full spectrum of negative outcomes requires complex `UNION ALL` statements across isolated Fact tables.

**Proposed Solution:**
Consolidate all operational outcomes (Rejected, Expired, Invalidated, Executed) into a single, comprehensive `fact_theoretical_signals` table.

**Why:**
Radically simplifies the quantitative research workflow.

**Benefits:**
- Single source of truth for all "What-If" backtesting scenarios.
- Plugs the data leak of the completely missing `INVALIDATED` signals.

**Trade-offs:**
- Requires careful query filtering in BigQuery (`WHERE status = 'REJECTED_BY_FILTER'`) to isolate specific subsets instead of natively clean siloed tables.

---

## 4.5. The Rollup Anti-Pattern (Data Round-Tripping)
**Current Problem:**
`agg_strategy_daily.py` and `performance.py` extract data out of BigQuery into Python memory, perform calculations, and push the results back into BQ staging tables via the Python `MERGE` framework.

**Proposed Solution:**
Eradicate the Python rollup scripts. Replace them entirely with Native BigQuery Materialized Views (e.g., `CREATE MATERIALIZED VIEW agg_performance`).

**Why:**
Executing SQL logic by pulling the dataset to a remote Cloud Run instance is an architectural anti-pattern that drastically increases latency, bandwidth costs, and external failure surfaces.

**Benefits:**
- Instantaneous updates natively within the data warehouse.
- Zero compute overhead requested from the Python Cloud Run worker.

**Trade-offs:**
- Moves transformation logic from version-controlled Python `.py` scripts to SQL schema definitions (Requires maintaining `.sql` files within the repository).

---

## 4.6. Asynchronous Fee and Price Resolution
**Current Problem:**
`TradeArchivalPipeline` captures closed trades instantly, but broker fees and fill prices are often delayed. `fee_patch.py` and `price_patch.py` currently run asynchronous SQL `UPDATE` operations mapping directly against `fact_trades` later in the lifecycle.

**Proposed Solution:**
Retain this decoupled approach, as asynchronous patching is required for eventual consistency. However, add an `is_finalized` boolean contract to the `TradeExecution` Pydantic schema so analysts definitively know whether the row can be trusted for final tax accounting.

**Why:**
Financial APIs guarantee latency on fills, but do not guarantee synchronicity on fee/commission settlement reporting.

**Benefits:**
- Allows real-time archival/leaderboards of the initial trade while cleanly handling delayed broker accounting.

**Trade-offs:**
- BigQuery analytic queries run at T+0 might show $0.00 fees until the T+1 patch successfully merges.

---

## 5. Backward-Compatible Strategy Normalization

### 5.1. The strategy_id UUID Bridge (Issue #365)
**Problem:**
After the migration to UUID `strategy_id` values (Issues #363 and #364), historical rows in `fact_trades` (which use pattern-name strings like `"BULLISH_ENGULFING"`) will no longer match the new UUID-based `dim_strategies` in JOIN operations. This causes historical performance data to "vanish" from dashboards.

**Solution:**
Implement a backward-compatibility bridge via a BigQuery View, `vw_fact_trades`. This view uses a `COALESCE` logic to map legacy pattern-name `strategy_id` values to their corresponding UUIDs by looking up the newly added `pattern_name` column in `dim_strategies`.

**Artifacts:**
- **`dim_strategies.pattern_name`**: A new column in the dimension table storing the human-readable pattern name associated with the strategy.
- **`vw_fact_trades`**: The primary analytical view for all trade-related dashboards.

```sql
-- Logic overview
COALESCE(
    d_direct.strategy_id, -- If strategy_id is already a UUID match, use it
    d_by_name.strategy_id, -- Otherwise look up by pattern_name in dim_strategies
    t.strategy_id -- Ultimate fallback: keep the raw value
) AS strategy_id_normalized
```

**Benefits:**
- Restores 100% of historical trend data immediately upon deployment of UUID strategies.
- Transparent to downstream BI tools (Looker/Tableau); they simply query the view instead of the raw table.
