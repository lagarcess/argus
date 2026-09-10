# Today by the New York calendar: evidence (#586)

The fix is `6e82ce9f`: `src/argus/domain/market_data/new_york_clock.py` owns
the clock, and every reader of the user's today derives from it. Lane base and
current integration are both `6d8c8f93`. Everything here ran at `6e82ce9f` with
no provider key set, and no model or provider was called.

## A visible date changes: the retest confirmation card

A retest keeps the run's start and ends on today, and the card shows that
period. Asked at 20:17 EDT on 2026-09-09, a UTC host had already turned to
2026-09-10, so the card ended a day the user had not reached.

`drivers/frozen_backend.py` runs the memory-persistence API with the process
clock on UTC and the New York clock frozen at 20:17 EDT on 2026-09-09
(00:17 UTC on 2026-09-10). It seeds one conversation per language, each with a
finalized buy-and-hold run over 2024 made through the engine and the evidence
finalization path. `browser/seed.json` records the instant, the host date
(2026-09-10) and the New York date (2026-09-09).

`drivers/retest_card_proof.mjs` drives the web app from this worktree
(`NEXT_PUBLIC_ENABLE_SPANISH=true`, mock auth) with Playwright at 1280 CSS
pixels: command palette, search the symbol, the run dossier's "Retest with
current data" / "Volver a probar con datos actuales", then the confirmation
card.

- **en, TSLA** (`browser/en-1-dossier.png`, `browser/en-2-confirmation-card.png`):
  Period "Jan 1, 2024 → Sep 9, 2026", and the retest line
  "Jan 1, 2024 – Dec 31, 2024 → Jan 1, 2024 – Sep 9, 2026". The persisted card
  row reads "January 1, 2024 - September 9, 2026".
- **es-419, NVDA** (`browser/es-419-1-dossier.png`,
  `browser/es-419-2-confirmation-card.png`): Periodo "1 ene 2024 → 9 sept 2026".
  The persisted row reads "1 de enero de 2024 al 9 de septiembre de 2026".
- Both cards persist `retest_period.effective_date_range` ending `2026-09-09`
  (`browser/en-report.json`, `browser/es-419-report.json`).

## The same retest at the date a UTC host read

`drivers/retest_dates_probe.py` runs the real retest turn with no `today`
argument at two frozen instants, in both languages, and `retest_dates_probe.txt`
is its output. At 20:17 EDT on 2026-09-09 the period ends September 9, 2026. At
an instant whose New York date is 2026-09-10, the date the base read from a UTC
host at that same evening, the period ends September 10, 2026. The seeded run
and every other field are identical, so the host's date is the only input that
moved the card.

## Not shown in the browser

Relative periods typed into chat ("today", "this week", "the last 30 days",
"year to date", "since January") need the interpreter, which is a model call.
They are proven without one in `tests/test_new_york_today.py` at 20:17 EDT,
20:17 EST on 2025-12-31 and noon, together with the date each prompt shows the
model.
