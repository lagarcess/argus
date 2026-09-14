# Issue #609 browser proof: research lookup recovery

Captured on 2026-09-13 at code head `d819b09d` on branch
`claude/research-provider-retry-0a2c38`, lane base `codex/private-alpha-next`
at `3d379d3d`.

Spec: `web/e2e/issue-609-research-lookup-recovery.spec.ts`. Every API response
is scripted in the browser, so no provider or model was called.

```bash
cd web && PLAYWRIGHT_PORT=3609 ARGUS_EVIDENCE_DIR="$PWD/../docs/reports/evidence/609" bunx playwright test e2e/issue-609-research-lookup-recovery.spec.ts
```

Result: 4 passed (5.5s).

Re-validated at `78eaaae2`, after merging integration `cb81e494`, which brought
#615's support-address web files: 4 passed (5.5s). The screenshots were
captured at `d819b09d`; the merge changed the profile menu's support address
and the legal pages, not the recovery notice.

The screenshots show the founder's copy from 2026-09-13, which holds whether or
not an answer appears above the notice: "I couldn't finish looking that up just
now. Try again in a moment." and "I can't look that up right now.", with the
Spanish "No pude terminar de buscar eso en este momento. Intenta de nuevo en un
momento." and "No puedo buscar eso ahora.". The first capture, at `15b671d4`,
showed the earlier copy.

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
