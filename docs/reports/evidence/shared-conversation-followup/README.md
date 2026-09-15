# Shared conversation follow-up evidence

## Candidate and integration

- Product head captured: `bf15cc03`.
- Original integration base: `350e3dca8f573f5dfd61f1f753d8ed16a2724c9e`.
- Reconciled integration: `bed233b0cdc96366acc5fc9d5a8d9193723612af`.
- One-way merge: `1c7080379667556345f8dab7578eb45b211ee8d0`.
- No textual conflicts. Semantic overlap is PR #639's viewport portals in
  AdaptivePanel and the guest dialogs. Both sides retained. All five public and
  preview cases and seven receiver bridge cases passed after reconciliation.
- Latest reconciliation also includes PR #638, research asset identity through
  confirmation. The new fork still imports no executable artifact state. The
  affected research/confirmation/runtime checks were rerun: 67 passed, 14 hit a
  local SciPy Mach-O loading error (zero-fill section offset), including the
  clock-unavailable failure caused by that import. Linux CI owns the final
  unaffected-environment check. OpenAPI compatibility: 23 pass. Merged-tree
  modularity passes. No textual conflicts; both lanes retained.

## Attribution

ReceiptChart now enables the library logo and displays the TradingView notice
and link in a visible footer, in both public and preview views. Label and URL
derive from `web/lib/chart-attribution.ts`, also used by ResultEquityChart.
The three new regression tests failed before the fix and pass afterward.
The notice follows the [upstream NOTICE](https://github.com/tradingview/lightweight-charts/blob/master/NOTICE).

## Browser evidence

Provider-free `scripts/qa/sharing_604_fixture.py`, real owner/public receipt and
fork routes, synthetic memory store. Normal chat streaming is mocked. Flags
are enabled only in the local process. No model/provider calls.

Motion remains enabled (`no-preference`, screenshot animations `allow`). Only
the development Next.js portal is hidden. All screenshots were inspected.

| Language/theme | Width | Public | Preview |
| --- | --- | --- | --- |
| en dark | 390 | [Full](en-dark-390-public-390.png), [top](en-dark-390-public-top.png), [chart](en-dark-390-public-chart.png), [bottom](en-dark-390-public-bottom.png) | [Top](en-dark-390-preview.png), [chart](en-dark-390-preview-chart.png), [bottom](en-dark-390-preview-bottom.png) |
| en dark | 720 | [Full](en-dark-720-public-720.png), [top](en-dark-720-public-top.png), [chart](en-dark-720-public-chart.png), [bottom](en-dark-720-public-bottom.png) | [Top](en-dark-720-preview.png), [chart](en-dark-720-preview-chart.png), [bottom](en-dark-720-preview-bottom.png) |
| en dark | 1024 | [Full](en-dark-1024-public-1024.png), [top](en-dark-1024-public-top.png), [chart](en-dark-1024-public-chart.png), [bottom](en-dark-1024-public-bottom.png) | [Top](en-dark-1024-preview.png), [chart](en-dark-1024-preview-chart.png), [bottom](en-dark-1024-preview-bottom.png) |
| en dark | 1280 | [Full](en-dark-1280-public-1280.png), [top](en-dark-1280-public-top.png), [chart](en-dark-1280-public-chart.png), [bottom](en-dark-1280-public-bottom.png) | [Top](en-dark-1280-preview.png), [chart](en-dark-1280-preview-chart.png), [bottom](en-dark-1280-preview-bottom.png) |
| es-419 light | 390 | [Full](es-419-light-390-public-390.png), [top](es-419-light-390-public-top.png), [chart](es-419-light-390-public-chart.png), [bottom](es-419-light-390-public-bottom.png) | [Top](es-419-light-390-preview.png), [chart](es-419-light-390-preview-chart.png), [bottom](es-419-light-390-preview-bottom.png) |

The six selected turns span DCA backtest, research with sources, research without
sources, a long research answer, plain answer and calculation. The exact preview
matches the public payload; private IDs are absent; no non-analytics write occurs
on view; the source can be revoked. The public composer sends one follow-up,
records count-only try_argus, creates a different conversation and imports twelve
messages without the owner's note. Separate bridge tests exercise guest/account,
existing guest consent/cancel, retry identity, reload, revoke and conversion.

## Deterministic verification

- Frontend: 2,021 tests pass; production build passes; lint has zero errors
  (eight existing unused-variable warnings).
- Backend fork/fixture/runtime final selection: 18 pass, including six real
  PostgreSQL tests using an isolated empty schema clone, with no new migration.
- Prompt surface: nine tests pass. No model-facing instruction text changed.
- Earlier focused backend: 388 pass, 49 skipped; mocked eval harness: 270 pass;
  contract/fixture checks: 24 pass.
- Full backend initial run: 8,590 pass, 611 skip, 39 fail. All 39 failed cases
  pass when rerun with local dotenv disabled and localhost process permissions;
  the initial failures were environment contamination/sandbox limitations.
- All costs in this build: $0. Live acceptance is pending founder go for a
  maximum $1 total, one plain and one fresh-figures follow-up.

This is acceptance evidence, not a terminal readiness audit. CI and the single
Codex review must finish before that audit. The evidence-only commit preserves
the captured product tree; any runtime change requires affected revalidation.
