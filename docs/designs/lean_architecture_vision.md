# Lean Analytics System Architecture (PROPOSED)

## Vision & Architecture Roadmap

The following diagram maps the proposed **Lean Architecture** for the signal lifecycle. It drastically simplifies the BigQuery footprint (reducing tables from 28 to 8), guarantees idempotency via Temp Tables, and strictly separates **Actual Executions** from **Theoretical Signals** to power a clean Backtesting Engine.

```mermaid
flowchart TD
    SG[Signal Generator] -->|Passes Filter| FS_LS
    SG -->|Fails Filter| FS_RS

    subgraph Hot_Storage_Firestore [Hot Storage: Firestore]
        FS_LS[(live_signals)]
        FS_RS[(rejected_signals)]
        FS_P[(live_positions)]

        FS_LS -.->|Status: WAITING -> EXPIRED| FS_LS
        FS_LS -.->|Status: WAITING -> EXECUTED/INVALIDATED| FS_LS
        FS_LS -->|On Execution| FS_P
    end

    subgraph Temp_Tables [Cloud Run: In-Memory to BQ Temp Tables - RAM FOOTPRINT: Safe]
        TT_T[(temp_trades Auto-Drops on End)]
        TT_TS[(temp_theoretical_signals Auto-Drops)]
    end

    subgraph BQ_Warehouse [BigQuery Analytics Cost-Optimized]
        F_TR[(fact_trades Executed Only)]
        F_TS[(fact_theoretical_signals Rejected/Expired/Invalidated/Executed)]

        MV_ASD[(MV: agg_strategy_daily Native Materialized View)]
        MV_PE[(MV: agg_performance Native Materialized View)]
    end

    TA[/TradeArchivalPipeline Python/]
    BTA[/BacktestArchivalPipeline Python - New/]

    FS_P -->|Status=CLOSED| TA
    TA -->|Alpaca execution enrichment| TT_T
    TT_T -->|Direct MERGE| F_TR

    FP[/Fee/Price Patches Python/] -.->|Update| F_TR

    FS_LS -.->|Status=EXPIRED/INVALIDATED| BTA
    FS_RS -.->|Status=REJECTED_BY_FILTER| BTA
    FS_LS -.->|Archiving executed signals| BTA
    BTA --> TT_TS
    TT_TS -->|Direct MERGE| F_TS

    F_TR -->|Native BQ SQL Engine| MV_ASD
    F_TS -.->|Optional joining for full theoretical history| MV_ASD
    MV_ASD -->|Native BQ View| MV_PE

    FS_STRAT[(dim_strategies Firestore)] -->|strategy_sync.py Syncs Configs| BQ_DIM_STRAT[(dim_strategies Core logic lookup)]

    BQ_DIM_STRAT -.->|Analytics JOIN| MV_ASD

    classDef firestore fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#000
    classDef bqTemp fill:#f1f5f9,stroke:#94a3b8,stroke-width:2px,stroke-dasharray: 4 4,color:#000
    classDef bqFact fill:#ccfbf1,stroke:#0f766e,stroke-width:2px,color:#000
    classDef bqView fill:#dbeafe,stroke:#1e40af,stroke-width:2px,color:#000
    classDef improvement fill:#dcfce7,stroke:#166534,stroke-width:2px,color:#000

    class FS_LS,FS_RS,FS_P,FS_STRAT firestore
    class TT_T,TT_TS bqTemp
    class F_TR bqFact
    class F_TS improvement
    class BQ_DIM_STRAT,MV_ASD,MV_PE bqView
```

## Key Improvements Addressed

1. **The Staging Bloat Eradicated**: Notice that the `stg_*` tables are gone. They are replaced by the `Memory JSON -> BQ TEMP TABLE` blocks (dashed gray). The pipeline uses transient Temp Tables to perform the `MERGE` and drops them instantly. Zero duplicate rows, zero UI clutter.
2. **The `INVALIDATED` Orphan Gap Fixed**: The dashed green line shows `INVALIDATED` signals now correctly mapping into the archival pipeline rather than rotting in Firestore.
3. **The `fact_theoretical_signals` Super-Table**: We've collapsed `fact_rejected`, `fact_expired`, and `fact_invalidated` into a single, unified backtesting repository (`fact_theoretical_signals` - highlighted in green). This lets your Backtesting Engine trivially query *"Show me all signals that failed gate criteria across all strategies."*
4. **Native BigQuery Views**: The orange / dark blue `agg_strategy_daily` and `summary_strategy_performance` logic has been moved *into* BigQuery as Native Views. We delete `agg_strategy_daily.py` and `performance.py` entirely, preventing the "round-tripping" anti-pattern where data leaves BQ just to be aggregated and shoved back in.
5. **Real Separation of Concerns**: We have rigorously separated `fact_trades` (your literal money/Alpaca performance) from your theoretical data. You will no longer risk "paper" metrics polluting your real win rates.
