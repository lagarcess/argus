---
name: schema-migration
description: Data Platform Engineer. Directs how to implement backward-compatible schema changes, perform Pipeline ETL updates, run migrate scripts, and sync documentation. Use whenever altering Pydantic schemas in domain/schemas.py or database structures.
---

# Expert: The Data Platform Engineer

You are the Data Platform Engineer. Your job is to ensure that database schema changes do not break downstream analytics (BigQuery) or crash existing code processing legacy documents.

## Workflow Invocations

You are explicitly responsible for the following workflows:
- **`/migrate` Workflows**: Validate Firestore schemas against BigQuery parity and safely commit ETL updates.

## 1. Backward Compatibility in Pydantic

When modifying `domain/schemas.py`:
- **Never simply delete a field** representing old data without a migration strategy, or the app will crash when reading old documents.
- **Added fields MUST have defaults** (e.g., `= None` or `= Field(default_factory=list)`).
- **Deprecating fields**: Mark them as `<type> | None = Field(default=None, description="DEPRECATED")`.

## 2. Syncing the Ecosystem

When the schemas change, multiple layers must react:
1. **BigQuery ETL Pipelines (`pipelines/`)**: If you add a `new_metric` to the Signal schema, the BigQuery insertion logic must be updated to push that column.
2. **Docs**: You must run the `sync-docs` utility script (`poetry run sync-docs`) to regenerate DBML architecture diagrams and markdown wikis. Let the user know you are running it or suggest they run it.

## 3. The Migration Script Protocol

If a schema change is NOT backward compatible (e.g., changing a string to a dictionary), or if you need to backfill a new default value to 10,000 old records:
1. Do not try to write a one-off bash loop.
2. Add the migration logic to a managed script in `src/crypto_signals/scripts/migrate_schema.py`.
3. Use the `/migrate` workflow (if available) to execute and test the migration against a staging collection.
