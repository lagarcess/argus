# Data Pipelines V2.5

> [!IMPORTANT]
> **Source of Truth**: For detailed schema and field definitions, refer to the [Data Handbook](./00_data_handbook.md).

## Philosophy: "The Golden Thread"
The **Golden Thread** is the happy path of data flow that proves the system is healthy.
**Signal -> Hot Storage -> Cold Storage -> BI**.

---

## 1. Architecture Decisions

### ETL vs. ELT
*   **Decision**: **ETL (Extract - Transform - Load)**.
*   **Reasoning**: We prioritize **Schema Safety** over raw loading speed.
    *   *Extract*: Low-latency fetch from Firestore/Alpaca.
    *   *Transform*: **Pydantic Validation (`SchemaGuardian`)** happens *in-flight* within the Python pipeline. This ensures "Garbage In" never reaches BigQuery.
    *   *Load*: Cleaned, typed JSON injected into BigQuery.
*   **Contrast**: We rejected ELT (Load raw JSON -> Transform in SQL) because it makes "Data Quality" a downstream problem.

### Latency Tiering
*   **Real-Time (Hot)**:
    *   **Signal Generation**: < 100ms (Firestore).
    *   **Order Execution**: < 500ms (Alpaca API).
*   **Batch (Cold)**:
    *   **Archival Loops (A, B, C)**: Daily (Post-market Close).
    *   **Reason**: Crypto 1D candles close at 00:00 UTC. We process the batch then.

### Storage & Partitioning
*   **Staging Strategy**: **Ephemeral In-Memory**.
    *   We do *not* use persistent Staging Tables (e.g., `stg_trades`).
    *   Data is "staged" in Python memory as Pydantic Objects.
    *   *Correction*: If volume scales to "100s of assets", we may introduce `stg_` BQ tables, but for current scale, direct insert is cheaper/simpler.
*   **Partitioning**: All BigQuery tables partitioned by `ds` (Date).

---

## 2. Core Pipelines (The 4-Loop Architecture)

### Loop A: Trade Archival (Happy Path)
*   **Source**: `live_positions` (Firestore).
*   **Target**: `fact_trades` (BigQuery).
*   **Logic**:
    1.  Fetch `CLOSED` positions from Firestore.
    2.  Fetch "Broker Validation" (Fill Price, Fees) from Alpaca.
    3.  **SCD Check**: Verify which `strategy_id` version generated this.
    4.  Insert to BQ.

### Loop B: Rejected Signal Archival (Shadow Loop)
*   **Source**: `rejected_signals` (Firestore).
*   **Target**: `fact_rejected_signals` (BigQuery).
*   **Extraction Logic**:
    *   **Time Window**: Extracts signals created > 7 days ago (`validity_window`).
    *   **Reason**: We need ~7 days of future market data to calculate `theoretical_pnl`. Extracting immediately yields no data.
*   **Business Logic**: Capture *why* we didn't trade (`rejection_reason`) + Theoretical P&L.

### Loop C: Expired Signal Archival (Noise Loop)
*   **Source**: `live_signals` (Expired).
*   **Target**: `fact_signals_expired` (BigQuery).
*   **Logic**: Calculate `max_mfe` (Did we miss a moonshot?) and archive.

### Loop D: Account Snapshot (Pulse Check) ✅
*   **Status**: Implemented (Issue #196, PR #205, #207)
*   **Source**: Alpaca Account API.
*   **Target**: `snapshot_accounts` (BigQuery).
*   **Logic**: Daily "End of Day" snapshot of Equity, Margin, and Greeks.
*   **Orchestration**: Runs daily via `main.py`, checks last run date to prevent duplicates.

---

## 3. Maintenance Pipelines (Data Patches)
*These pipelines run ad-hoc or on specific schedules to heal data quality issues. (Documented in **Issue #187**)*

### Fee Patch (`fee_patch.py`)
*   **Objective**: Reconcile estimated fees with actual T+1 settlement data from Alpaca.
*   **Trigger**: Daily (T+1).
*   **Target**: Updates `fact_trades.actual_fee_usd` and sets `fee_finalized=True`.

### Price Patch (`price_patch.py`)
*   **Objective**: Fix missing or zero fill prices in `live_positions`.
*   **Trigger**: Ad-hoc (when `entry_fill_price` is null).
*   **Target**: Updates Firestore `live_positions` from Alpaca Order API.

---

## 4. Orchestration & Monitoring
*   **Scheduler**: Cloud Scheduler (cron).
*   **Executor**: Cloud Run Jobs.
*   **Logging**: Cloud Logging (Structured JSON).
*   **Metrics**: Custom `job_metadata` table in Firestore tracks every run's `git_hash` and `status`.
