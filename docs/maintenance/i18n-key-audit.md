# i18n Key Consistency Audit

**Date:** 2026-06-11
**Auditor:** Jules

## Summary
An audit of the English (`en`) and Spanish Latin America (`es-419`) locale key consistencies was performed.

* **Total keys checked:** 446 keys
* **Missing in Spanish:** 0
* **Missing in English:** 0
* **Placeholders with drift:** 0
* **Invalid JSON files:** 0
* **Fixed keys:** 0

## Files Inspected
- `web/public/locales/en/common.json`
- `web/public/locales/es-419/common.json`

## Missing Keys by Locale

**Spanish (`es-419`)**
* None.

**English (`en`)**
* None.

## Placeholder Drift
No placeholder drift was detected between the two locales. All keys containing placeholders (like `{{count}}`, `{{account_hint}}`) match perfectly in structure and order between English and Spanish.

## Mechanical Fixes Applied
- None needed in this run.

## Items Needing Owner/Product Review
- None.

## Verification Checks Run
- JSON structure validation on `en/common.json` and `es-419/common.json`.
- Missing keys check script (comparing flattened object keys) via `spanish-ui-smoke.test.ts`.
- Placeholder drift detection script via `spanish-ui-smoke.test.ts`.

## Follow-up Recommendations
- **Automated tests:** A static locale parity guard test has now been integrated into `web/__tests__/spanish-ui-smoke.test.ts`. It compares flattened locale keys and checks for placeholder drift between the two files.
- **Continuous Missing Key Checks:** With the `spanish-ui-smoke.test.ts` update, this is now built into the CI pipeline.
