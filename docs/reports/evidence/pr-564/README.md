# PR #564 browser evidence: decisions attach to computations

Captured 2026-09-08 at worker head `502b6142` (integration `3d663402`
reconciled one way). The evidence commit adds only this folder, so the runtime
these captures vouch for is unchanged by it.

## Environment

- Backend: dev mode (memory persistence, synthetic unit fixtures, mock auth)
  on port 8010, with the integration OpenRouter key and model tiers so one
  real interpreter turn could run. The savings-projection harness kernel from
  `tests/computation_harness.py` was registered in-process and one
  conversation was seeded with a computed answer declaring
  `metadata.computation`. Nothing was persisted durably.
- Web: `next dev` on port 3100 with mock auth and Spanish enabled. Language was
  switched through the profile (`PATCH /me`), which is what the app applies.
- Driver: headless Chromium via Playwright at 1280 by 900. No credential appears
  in any capture or request log.

## Computed answer (new surface)

| File | What it shows |
| --- | --- |
| `computed-answer-offer-en.png` | A plain assistant answer that declares a computation offers Add decision under the message. No result card exists in this conversation. |
| `computed-answer-editor-en.png` | The same chips, note, and Save decision row the result card uses, mounted under the answer. |
| `computed-answer-saved-en.png` | After save, the answer carries Decision: Promising, rendered from the backend stamp. |
| `computed-answer-offer-es-419.png`, `computed-answer-saved-es-419.png` | The saved state in Spanish, Decisión: Prometedora, after a reload with the profile language switched. |

The decision behind these captures was recorded through
`POST /conversations/{id}/messages/{id}/decision`; the backend re-ran the
harness computation on open. The API proof for retrieve and re-run with changed
inputs is `tests/test_decision_attachment_api.py`.

## Result card (existing surface, behavior preserved)

One live interpreter turn, "Backtest AAPL from 2024-01-01 to 2024-12-31 with
$10,000", confirmed through the Run backtest chip on synthetic fixture data.

| File | What it shows |
| --- | --- |
| `result-card-offer-en.png` | The finished result card with Explain result, Refine idea, and Add decision in its action rail, as before. |
| `result-card-editor-en.png` | The decision editor opens below the rail in its original position and shape. |
| `result-card-saved-en.png` | Decision: Promising in the rail, and the earned memory proposal ("Remember this saved decision?") still fires after the save. |
| `result-card-saved-es-419.png` | The saved card in Spanish, Decisión: Prometedora, after a reload with the profile language switched. |
