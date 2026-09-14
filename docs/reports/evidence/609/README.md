# Issue #609 browser proof: research lookup recovery

Captured on 2026-09-14 on branch `claude/research-provider-retry-0a2c38`, in
the merge that brought integration `codex/private-alpha-next` at `98df2dbb`
(#607's answer without the lookup) and built founder decision 5. The first
capture, 4 cases, was at `d819b09d` and re-validated at `78eaaae2`.

Spec: `web/e2e/issue-609-research-lookup-recovery.spec.ts`. Every API response
is scripted in the browser, so no provider or model was called.

```bash
cd web && PLAYWRIGHT_PORT=3609 ARGUS_EVIDENCE_DIR="$PWD/../docs/reports/evidence/609" bunx playwright test e2e/issue-609-research-lookup-recovery.spec.ts
```

Result: 6 passed (9.4s).

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
| English, mobile, dark, transient failure, answered without the lookup | `en-mobile-dark-transient-answered-live.png` shows the answer from Argus market data with the amber notice and Retry under it; `-reloaded.png` shows the same after a reload; `-retried.png` shows the looked-up answer after Retry, with the earlier answer and its notice gone |
| Spanish, desktop, light, refused request, answered without the lookup | `es-419-desktop-light-refused-answered-live.png` and `-reloaded.png` show the answer with the quiet notice under it and no Retry |

Each case also asserts:

- a refused lookup makes exactly one stream request and offers no Retry;
- a transient lookup's Retry sends the persisted question verbatim, the notice
  is replaced by the answer, and the user's turn is not duplicated after the
  retry or after a reload;
- an answer given without the lookup stays visible with its notice below it,
  live and after a reload, and a case without one never shows it;
- no unexpected API request and no console error.

The same contract is proven against the real research rail and chat route with
scripted provider failures (HTTP 500, HTTP 429 with Retry-After, a timeout,
HTTP 400 and a missing key), with the answer without the lookup scripted where
it runs, in `tests/research/test_provider_failure_recovery.py`.

Two existing browser specs, `issue-313-retryable-failure-highlight` and
`chat-action-recovery`, fail the same 20 cases on the base web files at
`3d379d3d` as on this head (their mocks do not answer the memory availability
and conversation activity endpoints). CI runs neither; the fix is tracked
separately.
