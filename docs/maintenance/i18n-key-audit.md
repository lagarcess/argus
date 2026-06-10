# i18n Key Consistency Audit

**Date:** 2026-06-09
**Auditor:** Jules

## Summary
An audit of the English (`en`) and Spanish Latin America (`es-419`) locale key consistencies was performed.

* **Total keys checked:** 375 keys (approx.)
* **Missing in Spanish:** 1
* **Missing in English:** 0
* **Placeholders with drift:** 0
* **Invalid JSON files:** 0
* **Fixed keys:** 1

## Files Inspected
- `web/public/locales/en/common.json`
- `web/public/locales/es-419/common.json`

## Missing Keys by Locale

**Spanish (`es-419`)**
* `settings.dev.reset_onboarding` (Missing. It was present in English but missing in Spanish.)

**English (`en`)**
* None.

## Placeholder Drift
No placeholder drift was detected between the two locales. All keys containing placeholders (like `{{count}}`, `{{account_hint}}`) match perfectly in structure and order between English and Spanish.

## Mechanical Fixes Applied
- Added `settings.dev.reset_onboarding` to `es-419` with the translation `"Restablecer onboarding (dev)"`.
- The `web/public/locales/es-419/common.json` file was also automatically formatted to align exactly with the English structure for better maintainability (e.g., fixed indentation on `status` block).

## Items Needing Owner/Product Review
There were no ambiguous missing keys or non-trivial missing translations that needed to be deferred. All missing keys were strictly mechanical and fixed.

## Verification Checks Run
- JSON structure validation on `en/common.json` and `es-419/common.json`.
- Missing keys check script (comparing flattened object keys).
- Placeholder drift detection script.

## Follow-up Recommendations
- **Automated formatting:** Consider adding an automated step to `bun run lint` or Husky hooks that normalizes JSON key order in `es-419/common.json` to match `en/common.json`. This would prevent minor key ordering drift and make diffs cleaner in the future.
- **Continuous Missing Key Checks:** Consider using a tool like `eslint-plugin-i18next` or a dedicated i18n key consistency script to fail CI builds if keys get out of sync.
