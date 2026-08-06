# PR #363 Retest button and job-state evidence

The original state matrix was captured from the reconciled product tree at
`886521521c779ae2a1468407f7953fd960c63972` after merging
`origin/codex/private-alpha-next` at
`9760ac0d4cdd6a6e1c7bafd2b508fc925da29298`.

The accessibility and tooltip evidence was refreshed from the final UI tree at
`222ebd729173c26a07eba224a458bd6ebed0bd93`:

- `en-new-data-tooltip.png` and `es-419-new-data-tooltip.png` show that only the
  actionable new-data state exposes reusable-setup help on hover.
- `en-same-period.png` and `es-419-same-period.png` show the disabled state with
  its reason directly below the button and no contradictory tooltip. The same
  browser check verified that the button's `aria-describedby` points to that
  visible reason.

The screenshots use deterministic owner-scoped API fixtures and the real
Omnisearch dossier, confirmation, chat transport, polling, and backtest job-card
components. No provider, LLM, simulation, or hosted environment was called.

The original capture pass completed with 10/10 Chromium checks:

- English and es-419 dossier states: new data, same period, clamp-start repair,
  and unsupported timeframe.
- English and es-419 post-click job states: queued, running, and result ready.

The focused accessibility refresh completed with 4/4 Chromium checks (two
locales for the actionable tooltip and two locales for the same-period disabled
state). The actionable captures stop at hover and never click Retest.

## Retest receipt continuity

The post-submit receipt was refreshed from the product code committed at
`6300996c9de36c718bf7fd95101467d5aa9553d6`:

- `en-retest-receipt-pending.png` and `en-retest-receipt-ready.png` show one
  English receipt shell before and after the backend-owned context arrives.
- `es-419-retest-receipt-pending.png` and
  `es-419-retest-receipt-ready.png` show the equivalent Spanish transition.
- `en-mobile-multi-retest-receipt-pending.png` and
  `en-mobile-multi-retest-receipt-ready.png` cover the supported five-symbol
  shape in a 390px English viewport.
- `es-419-mobile-multi-retest-receipt-pending.png` and
  `es-419-mobile-multi-retest-receipt-ready.png` cover that same narrow shape
  with the longer Spanish label and context.

The deterministic Chromium check rendered the real `ChatMessage` and
`RetestReceipt` components, held the response in its optimistic state, and then
supplied a literal structured receipt. In both locales it verified that the
same DOM receipt node remained mounted and the context row remained present.
Desktop one-symbol receipts stayed `101.296875px` high before and after
hydration. The five-symbol mobile receipt stayed `139.296875px` in English and
`159.59375px` in Spanish, each with a `0px` height delta. Both narrow context
rows measured `95px` with `scrollHeight == 95px`, so the supported content fit
without clipping or overflow. Width remains intentionally content-sized.

This receipt capture made no API, provider, LLM, simulation, or persistence
call. Its development-only fixture was removed before the evidence commit.

The capture-only Playwright fixture was removed after the evidence was written;
only these durable artifacts are part of PR #363.
