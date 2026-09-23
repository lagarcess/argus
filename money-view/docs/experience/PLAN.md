# Argus finance experience

Owner: main task, architecture and integration captain. Base: private integration
`5430d98d61d815e6c4a2bed60213b411a2bb875e`. Working branch:
`codex/argus-finance-experience`. The only PR destination is
`codex/money-placement-pilot`.

## Intended result

Argus is the product. Its money view and conversation share one workspace. A
person can inspect an account, ask a question, review a proposed change, confirm
it, and revisit the same artifact in either surface. Existing finance domains,
settings and receipts stay reachable. Spanish and English receive the same care.

Production, `main`, `codex/private-alpha-next`, production environment files,
Supabase migrations and deployment are forbidden. Fixtures and local identity
remain the offline delivery path. Financial execution remains simulated.

## Work board

- [x] Ground: read Argus canon and design, inspect the current preview, trace
  existing frontend/runtime/file intake owners.
- [x] Sketch: compare two integration shapes and record the chosen interfaces.
- [x] Implement: reuse Argus interaction primitives; integrate chat, recall,
  guest entry, verified currency and statement import with current domains.
- [ ] Inspect: compare actual desktop, tablet and mobile screens to Argus;
  exercise keyboard, focus, hover, loading and recovery states.
- [ ] Verify: focused behavior tests, full local regression, browser journeys,
  scoped independent reviews and GitHub review to clean acknowledgment.
- [ ] Deliver: merge only into private integration, preserve screenshots and
  state precisely what is implemented, simulated and unverified.

## Grounding

Argus's `ChatInterface` is a large Next.js/Supabase controller. Its composer,
message presentation, scroll behavior, action rows, adaptive panels and
Omnisearch interaction are reusable; importing its application bootstrap would
also load production-oriented configuration. Copy/adapt these presentation
owners into the local app with explicit provenance, rather than importing the
bootstrap. No parallel local implementation of account balances or domain writes.

The generic Argus tool declaration/catalog/result-card boundary is reusable.
The seven-intent interpreter and executable confirmation are strategy-specific,
so a finance action needs a neutral typed proposal, not a fabricated strategy.
Money remains Decimal/integer minor units, including JPY and KWD. Currency
selection needs an owned account reference and explicit provenance.

Argus's feedback attachment picker does not upload file bytes. The finance
ledger already owns bounded previews and atomic import commits. Extend that
owner with explicit bank-column mapping and safe parsing; do not claim a
document pipeline exists. File contents are untrusted data, never instructions.

Jev is a nongenerative classifier. Its OpenRouter Decisions API differs from
chat completions. Investigate it inside the semantic boundary; a classifier
cannot replace arbitrary amount/date extraction or authorize writes. Published
vendor speed figures are not measurements of this application.

## Visual diagnosis

| Before | After | Why |
| --- | --- | --- |
| Finance navigation dominates every screen | Argus navigation gives chat, money and recall clear places | Reduce control-panel density without hiding capabilities |
| Assistant opens as a form modal | Full conversation canvas and persistent Argus composer | Preserve conversation continuity and useful screen space |
| Global search only finds transactions | Omnisearch with keyboard selection, grouped results and previews | Reopen the artifact or conversation the person remembers |
| Forest color carries almost every state | Cream/forest foundation with Argus muted semantic tokens | Let positive, negative and attention states remain distinct |
| Sidebar, header and forms compete at narrow widths | Adaptive navigation and content-first mobile layouts | Prevent a squeezed desktop from becoming the mobile product |
| Decorative sparkles and wordmark dot | Existing Argus wordmark and restrained functional controls | Restore the product identity |

## Acceptance

Guest entry leads into a local owned workspace. Money home remains useful
without a chat turn. A conversation can read real local records and propose
finance artifacts; only confirmed typed proposals call the existing domain
writers. Retry, reload and role/data changes cannot duplicate or resurrect a
write. Recall reopens the same record. A selected account supplies currency;
explicit currency changes remain visible and never silently convert balances.
CSV/TSV statement intake maps, previews and commits through the ledger, with
bounded adversarial-input handling and duplicate review.

Visual evidence covers both languages at 1440, 1024, 768, 390 and 320 pixels,
including money home, chat, Omnisearch, settings and import. A passing overflow
check alone does not establish visual quality. Live model quality, Jev latency,
hosted identity/providers and production deployment remain separate evidence.
