# Browser walk

`drivers/walk.mjs` drives the web app against the evidence API
(`drivers/serve.py`, with the recorded smoke conversations restored from
`turns/` and the failure scenes seeded), each step in English and Spanish at
1280 and 390 CSS pixels. Every step records its screenshots, what it should
show and whether it passed; each report below has a table beside its JSON.

| Report | Head | Steps | Passed | Failed | What ran |
| --- | --- | --- | --- | --- | --- |
| [walk-report.md](walk-report.md) | dc8608c8 | 52 | 46 | 6 | The full walk. |
| [walk-report-mobile-rerun.md](walk-report-mobile-rerun.md) | dc8608c8 | 12 | 12 | 0 | The no-solution, search dossier and Ask Argus steps again, after the walk learned to open search from the sidebar on a phone and to record a card an earlier width already repaired. |
| [walk-report-dossier-rerun.md](walk-report-dossier-rerun.md) | 5568a0b0 | 4 | 4 | 0 | The search dossier step again, on the notice fix, previewing the dossier on hover at 1280. |

## What the runs found

- The first walk's six failures were all at 390 and all came from the walk,
  not the app. The search dossier and Ask Argus steps pressed a desktop
  keyboard shortcut on the touch page, where search opens from the sidebar,
  and the no-solution step found its seeded card already repaired by the 1280
  step in the same conversation. The mobile rerun passed all three steps.
- The mobile rerun's 390 dossier showed a real layout bug in this lane's
  notice: in the saved answer, the message ran one word per line under an
  overlapping repair button. 5568a0b0 lets the notice wrap its action below
  the text, and the dossier rerun shows it fixed.
- At 1280 the first two runs clicked the search result, which opens the
  conversation on a wide screen, so their dossier screenshot showed the
  conversation. The dossier rerun hovers instead and captures the dossier pane.
- The backtest step: en 1280: ran; en 390: already ran; es-419 1280: ran; es-419 390: already ran.

A screenshot keeps one file per step, language and width, so a later run
replaces the earlier file for the same step; the latest report that names a
file describes it.

## Spend

The walk's route receipts total $0.00681, under its $0.25 hard stop; the
reruns spent nothing. No chat turn was sent: the Ask Argus step shows the row
without sending it.
