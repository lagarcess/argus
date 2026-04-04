---
description: Validates Firestore schemas and BigQuery parity, then commits changes.
---

1. **Schema Diffing**
   - Identify which Pydantic models in `src/crypto_signals/domain/schemas.py` were modified.
   - Does this change require backfilling old Firestore documents? (If yes, confirm `migrate_schema.py` is updated).

2. **BigQuery Parity Check**
   - Check the ETL pipelines in `src/crypto_signals/pipelines/` (e.g., `trade_archival.py`).
   - If a new field was added to the Domain Schema, did you also add it to the BigQuery mapping dictionaries?
   - **Constraint**: If BigQuery is not updated, the pipeline will crash on insert. Fix it now.

3. **Documentation Sync**
   // turbo
   - Run the automated doc generation to sync the architecture diagrams and wikis.
   - Execute: `poetry run sync-docs`

4. **Migration Dry Run (Optional but Recommended)**
   // turbo
   - If applicable and safe: `poetry run python -m crypto_signals.scripts.migrate_schema --dry-run`
   - Review output.

5. **Commit & Notify**
   - Inform the user that the schema has evolved successfully and downstream docs/pipelines are in sync.
