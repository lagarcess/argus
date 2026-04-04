# ADR: BigQuery Column Types for fact_theoretical_signals Nested Fields

## Status
Accepted

## Context
The `fact_theoretical_signals` table consolidates all signal outcomes into a single backtesting super-table. The `Signal` model contains nested fields that suffer from a NoSQL-to-SQL impedance mismatch:
- `confluence_snapshot`
- `harmonic_metadata`
- `structural_anchors`
- `rejection_metadata`

## Decision
We adopt a hybrid mapping strategy:

1. **`confluence_snapshot`** -> `STRING` (JSON blob)
   - Reason: Content has variable keys natively queried via `JSON_VALUE(..., '$.rsi')`.

2. **`harmonic_metadata`** -> `STRING` (JSON blob)
   - Reason: Ratio sets vary wildly by pattern type (e.g. Gartley vs Elliott). A rigid RECORD would force dozens of nullable columns.

3. **`structural_anchors`** -> `REPEATED RECORD`
   - Reason: Homogeneous arrays representing pivots (price, timestamp, pivot_type, index) that allow analytical deep dives (e.g., average pivot count). A dedicated `StructuralAnchor` Pydantic model generates the schema.

4. **`rejection_metadata`** -> `STRING` (JSON blob)
   - Reason: Forensic audit data rarely queried analytically.

## Consequences
- Requires `@field_serializer` intercepting the 3 JSON fields in Pydantic during BigQuery stringification so they pass as strings explicitly in `insert_rows_json`.
- `SchemaGuardian` has been patched to gracefully detect `Optional[List[StructuralAnchor]]` and establish the `REPEATED` mode correctly, despite Python `typing.Union` constraints.
