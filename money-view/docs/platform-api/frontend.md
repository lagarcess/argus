# Shared frontend contract

Feature pages use `PlatformPageProps` from `src/platform/types.ts`. Export each page by name from your feature `index.ts`. The shell alone owns navigation/session/theme and assistant visibility. Notify shell worker of final names. Routes use `#transactions?q=market`; `onNavigate(page, query)` preserves native browser Back and refresh.

- `request<T>(path, schema: z.ZodType<T>, options?: RequestInit)` from platform/client prefixes `/api/platform`, validates the response, and sends JSON Content-Type for body. Pass `body: JSON.stringify(payload)`. Errors are `APIError` with `.code` and `.status`. HTTP-only cookie is automatic. Do not silently swallow mutations.
- `useResource<T>(loader: () => Promise<T>, deps)` from platform/hooks returns `{data:T|null, error:Error|null, loading:boolean, reload:()=>void}`. Old results stay visible on explicit reload; changed dependencies clear the previous result immediately so a different currency or household cannot display stale numbers. Stale completions cannot overwrite new data. Include currency, query.toString(), revision in dependencies where used. A feature mutation calls local reload and `onChanged` for global invalidation.
- `PageHeader({title:string, eyebrow?:string, description?:string, actions?:ReactNode, children?:ReactNode})`.
- `Panel` accepts normal section HTML attributes, children and className.
- `Modal({title:string,onClose:()=>void,children:ReactNode,footer?:ReactNode,destructive?:boolean})`. Native dialog owns topmost focus, Escape, backdrop, scroll lock and focus restoration. No parallel page-level focus traps. Mark the Cancel button `data-modal-cancel` in destructive dialogs; initial focus prefers that marker and otherwise uses safe Close. Keep pending write state inside modal.
- `Field({label:string,children:ReactNode,help?:string,error?:string})`: one input/select/textarea per Field; native wrapping label.
- `EvidenceLine({evidence:Evidence,locale})`, `Money({amount:string|number,currency:string,locale})`.
- `EmptyState({title:string,description?:string,action?:ReactNode,children?:ReactNode})`.

Shared classes (scoped by `.platform-shell`): `p-button` primary, `p-button-secondary`, `p-button-ghost`, `p-button-danger`, `p-icon-button`; `p-actions`, `p-toolbar`, `p-form-grid`, `p-stack`, `p-field`, `p-muted`, `p-error`, `p-success`, `p-badge`; `p-metrics` and `p-metric` with small label/strong value; `p-ledger`, `p-ledger-row`, `p-row-main`, `p-row-value`, `p-row-actions`; `p-table-wrap` and `p-table`; `p-pagination`; `p-tabs`; `p-loading`. Forms automatically get 16px inputs and 44px controls. Use semantic tables, real labels, and one inline error owner. All copy supports en/es-419. No financial figure without adjacent EvidenceLine.

## Shell integration

All domain routes are lazily loaded. Household and login transitions reset the session resource epoch; active page and assistant mounts are keyed by user and household to prevent stale private records. Profile changes call `onChanged()` to reload session and financial revisions. The overview derives balances and cash flow from `/overview`; currency selection is a filter and never an FX conversion. Logout returns to explicit local profile entry.

The shell borrows Argus AdaptivePanel/native topmost focus ownership, context-contained settings, field labeling and reduced-motion patterns. Clara colors and typography remain isolated under `.platform-shell`. The old deposit styles remain in the bundle for the retained feature, with platform-specific overrides.

## Shell verification, 2026-09-20 local fixture

Production build (`npm run build`) passes with lazy feature chunks. Initial JavaScript is approximately 319 kB minified / 96 kB gzip; route bundles load on demand.

Manual actual-API browser checks used the dedicated local fixture API on 8012 and Vite on 5178. Overview document width stayed within its viewport at 1440, 1024, 768, 390 and 320 CSS pixels. Both system-dark and saved-light appearances were inspected; saved light persisted after reload. Native modal Shift-Tab stayed within the dialog, Escape restored the opener, and the body scroll lock returned to its prior value. Assistant opening showed the available prepared questions and unavailable free-text explanation without issuing a question. Hash navigation and immediate authenticated reload were exercised; native Back acceptance remains in the broader suite. Temporary browser tab and viewport override were cleaned up.

Vite originally rewrote Host and caused the local identity origin check to reject login. The browser-test owner corrected its proxy to preserve Host; all checks above followed that correction. Durable screenshots and broad bilingual/lifecycle acceptance remain owned by the integration browser test suite. This manual record does not replace that suite.
