# Issue #609 browser proof: research lookup recovery

Captured on 2026-09-13 at code head `15b671d4` on branch
`claude/research-provider-retry-0a2c38`, lane base `codex/private-alpha-next`
at `3d379d3d`.

Spec: `web/e2e/issue-609-research-lookup-recovery.spec.ts`. Every API response
is scripted in the browser, so no provider or model was called.

```bash
cd web && PLAYWRIGHT_PORT=3609 ARGUS_EVIDENCE_DIR="$PWD/../docs/reports/evidence/609" bunx playwright test e2e/issue-609-research-lookup-recovery.spec.ts
```

Result: 4 passed (5.0s).

Re-validated at `af271c47`, after the Codex review fix `c2819235` and the merge
of integration `6eb93d84`: 4 passed (5.5s). No file under `web/` changed after
`15b671d4`, and the spec scripts every API response, so the screenshots still
show that head's behavior.

| Case | Screenshots |
| --- | --- |
| English, desktop, light, transient failure (HTTP 500) | `en-desktop-light-transient-live.png` shows the amber notice with Retry; `-reloaded.png` shows the same notice after a reload; `-retried.png` shows the answer after Retry asked the same question |
| Spanish, mobile, dark, transient failure | The same three steps, with Spanish copy rendered from the code; the persisted English never shows |
| English, desktop, dark, refused request (HTTP 400) | `en-desktop-dark-refused-live.png` and `-reloaded.png` show the quiet notice with no Retry |
| Spanish, mobile, light, refused request | The same two steps in Spanish |

Each case also asserts:

- a refused lookup makes exactly one stream request and offers no Retry;
- a transient lookup's Retry sends the persisted question verbatim, the notice
  is replaced by the answer, and the user's turn is not duplicated after the
  retry or after a reload;
- no unexpected API request and no console error.

The same contract is proven against the real research rail and chat route with
scripted provider failures (HTTP 500, HTTP 429 with Retry-After, a timeout,
HTTP 400 and a missing key) in `tests/research/test_provider_failure_recovery.py`.

Two existing browser specs, `issue-313-retryable-failure-highlight` and
`chat-action-recovery`, fail the same 20 cases on the base web files at
`3d379d3d` as on this head (their mocks do not answer the memory availability
and conversation activity endpoints). CI runs neither; the fix is tracked
separately.
