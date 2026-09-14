# Issue #624 evidence

Integration base: `5cb360c1bb09ce75ab09559a47c7518026ef2fcf`.

`red.txt` records the regression against integration before production edits:
20 failures, including both the cents-bearing start and half-cent tie rendering
zero change. `green.txt` records 20 passing cases after the fix, across gains,
losses, zero, buy-and-hold, DCA, English, Spanish, and live/reloaded web mappers.
Run with `poetry run pytest tests/test_result_card_gain.py -q --no-cov`.
The test's DCA setup now uses the canonical explicit capital-plan builder.

The browser images show the actual `StrategyResultCard` with synthetic backend
card output. No provider, model, or paid backtest was invoked. `cards.json`
contains the two card fixtures; `page.tsx.txt` is the temporary browser harness.
To reproduce, copy both into `web/app/dev/issue-624/` (rename the page to
`page.tsx`), run Next dev, and open `/dev/issue-624?lang=en` and
`/dev/issue-624?lang=es-419`. Remove the temporary route afterward. It is not a
shipped product surface. The harness supplies its own i18n instance so account
language hydration cannot overwrite the requested fixture language.

Both images show $1 profit for the $1,000.50 start and $0.01 profit for the
DCA half-cent tie. Final-head revalidation and terminal CI/review evidence are
recorded on the PR after the review completes.
