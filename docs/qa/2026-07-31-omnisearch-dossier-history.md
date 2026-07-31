# Omnisearch dossier history acceptance

Issue: #309  
Branch: `codex/omnisearch-dossier-history`  
Locked base: `acbf1c3070f0e2b9dd3dd797eb80c119a87a6d6a`  
Browser candidate: `3000cee2516f7eb81ddf2a45aafd0c2658304b8d`

## Environment

The browser matrix used the real Next.js and FastAPI applications at
`127.0.0.1:58100` and `127.0.0.1:58101`. FastAPI used an in-memory,
mock-auth fixture with:

- seven evidence-backed completed runs and five decisions for the primary
  conversation;
- twenty-three evidence-backed completed runs and seven decisions for the
  pagination conversation;
- one exact persisted assistant-message anchor per run;
- synthetic market-data mode, memory persistence/checkpointing, blank provider
  keys, blank database URL, disabled background jobs and context packets, and
  loopback-only proxy/network settings.

This fixture added no endpoint, migration, or durable model. The frontend used
the real Omnisearch route and API client with the Omnisearch flag enabled.

## Browser acceptance

The following passed in both English and es-419 at 1440x900, and in both
languages at 390x844:

- the latest dossier kept one run's setup, metrics, decision, typed
  `run_fresh`, and result-message anchor together;
- the primary tally rendered as `5 of 7 decided` and
  `5 de 7 con decisión`;
- opening Decision history was the first dossier-history request;
- the loaded listbox owned keyboard focus, and ArrowDown then Enter selected
  an older run without changing `/chat`;
- a narrow-viewport pointer click selected an older history row without
  changing the route;
- undecided rows rendered as `No decision saved` /
  `Sin decisión guardada`;
- plain Enter preserved a note newline, while Command+Enter saved the decision,
  showed `Saved`, and refreshed both `/search` and `/run-dossiers` before the
  tally changed;
- `Open in conversation` navigated to the selected run's exact message query
  and focused the matching `data-message-id`;
- the first pagination read returned 20 unique rows, `Load older` sent one
  opaque cursor, and the second page produced 23 unique rows with no remaining
  load control.

The actual browser run found and closed two focus/layout issues before
acceptance:

1. async history loading initially left focus on `BODY`; the listbox now takes
   focus only when the user has not deliberately moved it elsewhere;
2. at 390x844 the history list initially had `clientHeight: 0`; the corrected
   history pane retained conversation access and produced a 95-pixel nested
   scroll viewport (`scrollHeight: 780`) in both locales.

Console evidence contained only the React development and HMR informational
messages, with zero warnings or errors in the final EN and es-419 sessions.
Final request logs contained only local locale assets and the expected Argus
`/me`, `/conversations`, `/messages`, `/history`, `/search`, `/run-dossiers`,
and decision endpoints. There were no agent, chat-stream, discovery, backtest,
LLM, research, market-data, or external-host requests.

## Evidence

Representative screenshots:

- `output/playwright/omnisearch-dossier-history/en-desktop-latest-dossier-final.png`
- `output/playwright/omnisearch-dossier-history/en-desktop-keyboard-selected-run06.png`
- `output/playwright/omnisearch-dossier-history/en-desktop-multiline-decision-editor.png`
- `output/playwright/omnisearch-dossier-history/en-desktop-saved-canonical-refresh.png`
- `output/playwright/omnisearch-dossier-history/en-desktop-exact-transcript-anchor.png`
- `output/playwright/omnisearch-dossier-history/en-desktop-pagination-first-page.png`
- `output/playwright/omnisearch-dossier-history/en-desktop-pagination-loaded-23.png`
- `output/playwright/omnisearch-dossier-history/en-mobile-history-scrollable-final.png`
- `output/playwright/omnisearch-dossier-history/en-mobile-selected-run06-final.png`
- `output/playwright/omnisearch-dossier-history/es-desktop-latest-dossier.png`
- `output/playwright/omnisearch-dossier-history/es-desktop-selected-undecided.png`
- `output/playwright/omnisearch-dossier-history/es-mobile-history-scrollable.png`
- `output/playwright/omnisearch-dossier-history/es-mobile-selected-run06.png`

Trace/network evidence:

- `output/playwright/omnisearch-dossier-history/.playwright-cli/traces/trace-1785496016310.trace`
- `output/playwright/omnisearch-dossier-history/.playwright-cli/traces/trace-1785496016310.network`
- `output/playwright/omnisearch-dossier-history/en-mobile-browser.trace`
- `output/playwright/omnisearch-dossier-history/en-mobile-browser.network`
- `output/playwright/omnisearch-dossier-history/es-browser.trace`
- `output/playwright/omnisearch-dossier-history/es-browser.network`

## Verification

The exact post-acceptance branch passed:

- `poetry run pytest tests/ -q`: 3,242 passed, 209 skipped, 87% coverage;
- hermetic agent-runtime and spine sweep: 1,439 passed;
- OpenAPI compatibility and Alpha artifact checks: 34 passed;
- `bun test`: 793 passed;
- ESLint: zero errors and one pre-existing unused-import warning in
  `ChatInterface.tsx`;
- Next.js production build, Ruff, modularity budget, generated OpenAPI
  comparison, environment topology, and diff hygiene: passed.

Disposable-Postgres-only tests remain explicitly skipped when
`ARGUS_DISPOSABLE_DATABASE_URL` is unavailable; no migration was added.
