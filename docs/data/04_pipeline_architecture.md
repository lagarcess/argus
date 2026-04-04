# 04. Pipeline Architecture & Strategy

> [!IMPORTANT]
> **Source of Truth**: Detailed storage schemas are co-located in the [Data Handbook](./00_data_handbook.md).

## 1. Architecture Strategy (ETL vs ELT)

We selected **ETL (Extract-Transform-Load)** over ELT for this phase.

*   **Decision Driver**: **Schema Safety & Data Quality**.
*   **Why**:
    *   In ELT, raw dirty data hits the warehouse first.
    *   In our financial system, we need **Guaranteed Types** (Decimal precision for PnL) *before* ingestion.
    *   **Pydantic** acts as the Transformation Engine in Python memory ("Ephemeral Staging"), ensuring only valid, typed, enriched rows reach BigQuery.

---

## 2. Latency & Throughput Tiering

| Tier | Latency Goal | Pipeline | Use Case |
| :--- | :--- | :--- | :--- |
| **Real-Time** | < 1 sec | **Signal Generation** | Market Data -> Signal -> Alpaca Order. |
| **Near Real-Time**| < 1 min | **State Sync** | Order Fills -> Firestore (`live_positions`). |
| **Batch** | Daily (T-0) | **Loop A (Trades)** | Closed Trades -> BigQuery (`fact_trades`). |
| **Batch (Shadow)**| Daily (T+7) | **Loop B (Rejections)**| Rejected Signals -> Re-analysis -> BigQuery. |

---

## 3. Storage Strategy

### Hot Storage (Firestore)
*   **Role**: **Operational State**.
*   **Retention**: Short-term (Active Signals + Recent History).
*   **Cleanup**: `cleanup_firestore.py` runs daily in `main.py` after export.
*   **Primary Key**: `signal_id` / `strategy_id`.

### Cold Storage (BigQuery)
*   **Role**: **Analytical History**.
*   **Retention**: Infinite (Append-Only).
*   **Partitioning**: Time-based (`ds` / partition key) to optimize cost/performance.
*   **Primary Key**: `trade_id` / `account_id` + `ds`.

---

## 4. Gap Analysis & Roadmap (Gap -> Fix)

| Gap | Severity | Fix Plan | Issue |
| :--- | :--- | :--- | :--- |
| **Orchestration** | Critical | **Loop B & C** are orphaned. **Loop D** needs hook (#196). | #183, #196 |
| **Data Integrity** | Critical | **Loop B (Rejections)** extracts at T-0 (too early). Need T+7 logic. | #181 |
| **Schema Drift** | High | BigQuery schema does not match Pydantic model (`fee_finalized` missing). | #191 |
| **Metadata** | Medium | Jobs run without `git_hash` trace. Need `job_metadata` enrichment. | #197 |

---

## 5. Future Optimizations (Phase 3+)
*   **Market Data Disk Cache**: To reduce API calls (Alpaca/Polygon) during backfills.
*   **Aggregated Views**: `agg_strategy_daily` materialized view for dashboard speed.
*   **Partition Expiry**: Auto-delete Staging data in BigQuery if we move to ELT.
