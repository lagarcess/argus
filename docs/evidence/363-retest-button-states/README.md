# PR #363 Retest button and job-state evidence

Captured from the reconciled product tree at `886521521c779ae2a1468407f7953fd960c63972`
after merging `origin/codex/private-alpha-next` at
`9760ac0d4cdd6a6e1c7bafd2b508fc925da29298`.

The screenshots use deterministic owner-scoped API fixtures and the real
Omnisearch dossier, confirmation, chat transport, polling, and backtest job-card
components. No provider, LLM, simulation, or hosted environment was called.

The capture pass completed with 10/10 Chromium checks:

- English and es-419 dossier states: new data, same period, clamp-start repair,
  and unsupported timeframe.
- English and es-419 post-click job states: queued, running, and result ready.

The capture-only Playwright fixture was removed after the evidence was written;
only these durable artifacts are part of PR #363.
