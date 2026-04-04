# Roadmap: Crypto Sentinel V2.0

## Vision
Evolve the system from a simple signal generator to a robust, strategy-agnostic trading platform with strict data governance ("Guardian") and enterprise-grade observability.

## Phase 1: Schema Safety (Guardian) - DONE
- [x] Implement `SchemaGuardian` to enforce Pydantic <-> BigQuery parity.
- [x] Centralize schema definitions.

## Phase 2: Cost Control & Cleanup - DONE
- [x] Integrate Firestore Cleanup (TTL).
- [x] Implement `ExpiredSignalArchival` (Loop C).

## Phase 3: Strategy Architecture (Current Focus)
**Goal**: Bridge the gap between "Hot" config (Firestore) and "Cold" analytics (BigQuery) using SCD Type 2.

### Active Issues (Jules)
- [ ] **#181**: Critical: Loop B T+7 extraction logic is incorrect.
- [ ] **#182**: Critical: Account ID Mismatch prevents data joins.
- [ ] **#183**: Critical: Orchestration Gap - Loop B & C Pipelines are ORPHANED.
- [ ] **#184**: Feature: Implement Aggregation Layer (agg_strategy_daily).
- [ ] **#185**: Safety: Guardian v2 - Enforce Partitioning & Clustering.
- [ ] **#186**: Hygiene: Implement Dual-Layer Cleanup Strategy.
- [ ] **#187**: Documentation: Sync Data Docs with Implementation.
- [ ] **#188**: Risk: Implement Correlation Risk Check.
- [ ] **#189**: Config: Enable GCP Logging by Default for Prod.
- [ ] **#190**: Perf: Implement Market Data Disk Cache.
- [x] **#191**: Critical: Schema Mismatch in fact_trades (Missing Columns) - *Resolved via `migrate-schema` CLI*.
- [x] **#192**: Critical: Order Execution Failed (Cost Basis < $10) - *Resolved via `_is_notional_value_sufficient()` check*.
- [x] **#193**: Critical: Discord Notification Failed (Forum Thread Requirement) - *Resolved via `_generate_thread_name()` helper*.
- [x] **#194**: Bug: False Negative Error Reporting - *Resolved via metrics refactor* (PR #204, #207).
- [x] **#195**: Feature: Strategy Sync Pipeline (SCD Type 2) - *Implemented* (PR #206, #207).
- [x] **#196**: Critical: Account Snapshot Orchestration (Loop D) - *Implemented* (PR #205, #207).
- [ ] **#197**: Ops: Metadata Enrichment (Git Hash & Config).
- [ ] **#198**: Tech Debt: Formalize Defaults in `dim_strategies`.

### Backlog / Drafts (Planned)
- [ ] **[Draft]**: Pattern Override Logic (Config-Driven).
- [ ] **[Draft]**: Strategy Risk Params (Migrate to Strategy-Specific).

## Phase 4: Operational Visibility
*(Pending Workflow Log Analyzer)*

## Phase 5: Advanced Risk Manager
- [ ] **#188**: Correlation Risk Checks.
- [ ] **#189**: GCP Logging Integration.

## Reference
See `task.md` and `implementation_plan.md` in the artifacts directory for detailed specifications.
