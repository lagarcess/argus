# PR #552 factual follow-up proof

The reviewed source is `6fd92c6500921d8e0d72f0faa03f54163c946353`. The API correction is `5ea47355bd2d3849cca0f0ece176fc7744e93c97`; the complete source, including history hydration, is `bb3bff50902a1dc221745fb4b0b87ab6b42f5b5d`.

| Language | Before: empty live answer | Before: generic reload | After: voiced fact | After: retained reload |
| --- | --- | --- | --- | --- |
| English | [Live](browser/before-en-empty.png) | [Reload](browser/before-en-reload.png) | [Live](browser/after-en-answer.png) | [Reload](browser/after-en-reload.png) |
| Spanish | [Live](browser/before-es-empty.png) | [Reload](browser/before-es-reload.png) | [Live](browser/after-es-answer.png) | [Reload](browser/after-es-reload.png) |

Both accepted after-cases have `response_intent.kind=beginner_guidance`, a root `result_fact_bank`, and the recorded peak date and value. The public persisted content exactly matches each live answer. [Proof and source hashes](browser/proof.json) identify the capture commits and explicitly retain the earlier English live capture because the later source change affects only history hydration.

The real browser calls the local API and live OpenRouter using founder-approved synthetic QA history and an existing completed META QA backtest. Persistence and auth are local memory and mock auth. No production database or real user content is used. [Replay launcher](browser/replay_api.py) reads the designated operator `.env` without writing it; run it from the repository root with `PYTHONPATH` and `ISSUE531_QA_SOURCE_ROOT` pinned to the source tree being measured.

The record includes the [failed backend-only reload](browser/backend-only-en-reload-incorrect.png), two English prose-guard recoveries, three correct answers from other paths that were excluded from P1 acceptance, and the unavailable fee probe. The latter exposed an English option label in the Spanish recovery. The English accepted response contains an em dash. Raw responses and screenshots are preserved unchanged; this proof does not claim those wording observations are fixed.

Validation: 104 focused backend/release checks, 1,556 frontend tests, and 237 mocked eval checks pass. Frontend regression tests failed before the hydration correction. The model-facing fingerprint is unchanged and no live eval suite was rerun. CI and follow-up review are reported on the PR at its final head.
