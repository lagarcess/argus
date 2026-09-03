# Issue #411 browser acceptance

See the [follow-up report](../../../2026-09-03-issue-411-followup.md) for the
regression decision, screenshots, environment boundaries, complete-suite
results, and integration dependency.

- `browser-evidence.json` joins all nine API turns to their full OpenRouter
  receipts, response metadata, provenance, and screenshot hashes.
- `route-receipts.jsonl` and `combined/route-receipts.jsonl` are copies from the
  API's existing receipt-persistence boundary.
- `.sse` files contain browser response bodies with final blank lines normalized.
  Transcript and test-output trailing whitespace is normalized for storage.
  Message JSON files are
  the API responses used when the UI reloaded after switching to headless.
- Screenshots are unedited. Text files retain full visible transcripts even
  where the scrollable chat extends beyond the screenshot viewport.
- `combined/` is verification of the prospective tree including integration
  `4e987de6`, not evidence that a branch was merged or deployed.

`observe_local_api.py` was run from the lane root with its existing Poetry
environment. It loads the existing root `.env` into the process, applies only
the documented local QA overrides, and writes observations to
`output/playwright/issue-411/`. For the combined capture,
`ISSUE411_QA_SOURCE_ROOT`, `ISSUE411_QA_OUTPUT`, and `ISSUE411_QA_TREE` selected
the temporary archive and its separate output directory. The web process used
mock auth, the local API origin, both locale support and the research rail,
and an isolated Next build directory. Browser storage state is deliberately
excluded from this committed evidence.
