# DOCN guest conversion refusal investigation

**#543 does not restore the conversion modal for this case.** It preserves a failed receipt and improves the explanation, but the conversion signal still disappears before SSE reaches the browser. This is an unresolved conversion defect, not solely a promotion decision. The two-run guest limit is intentional and was unchanged.

Investigated on 2026-09-05 UTC for the 2026-09-04 23:16 UTC DOCN incident in conversation `623011f3-7b89-4b1d-b6c3-cd7a99300c8c`. Production was not written to. This follow-up made no production requests and changed no product source.

## What the browser showed

| Scenario | Integration `5761dd417429895a24037df8231528c759af4179` | Production shape `c7802b37f39772a1216514e37fb6ff2b63142181` |
| --- | --- | --- |
| First and second Run | Both completed, persisted two runs, counter advanced 0 → 1 → 2 of 2 | Same |
| Third Run on the same visitor day | Conversion modal, zero `/chat/stream` requests | Same |
| Third Run after visitor-day rollover and Start over, with workspace counter still 2/2 | **No modal.** “Backtest could not finish” receipt plus “This guest workspace has used its simulation allowance, so the backtest did not start. Create an account to keep this setup and continue.” | **No modal.** “The backtest could not complete. Try again from the current setup or adjust it first.” |
| Rows after the next-day refusal, starting with cleared history | One failed job with `failure_code=account_conversion_required`; no run | No job; no run |
| Counter after refusal | Unchanged at 2/2 | Unchanged at 2/2 |

Browser screenshots:

- [Integration same-day modal](integration-third-same-day.png)
- [Integration next-day refusal](integration-third-next-day.png)
- [Production same-day modal](production-third-same-day.png)
- [Production next-day generic failure](production-third-next-day.png)
- [Integration second completed run](integration-run2.png), [production second completed run](production-run2.png)

## The precise loss

The suspected producer/consumer mismatch is real at the browser, but a bridge exists in between. The bridge is not the missing component.

1. Admission returns `conversion_required`.
2. Production's `admission_rejection_envelope` puts `account_conversion_required` in `capability_context.failure_code`.
3. `public_failure_code` and `failed_final_response_payload` copy it to the execute stage's `final_response_payload.code`. Integration's failed-receipt path also explicitly sets that same field.
4. `graph/workflow.py:_patched_run_state` calls `RunState.model_validate(payload)`.
5. `RunState.final_response_payload` is a `FinalResponsePayload`. That model has `result`, `backtest_job`, `error`, `summary`, `result_card`, and `explanation_context`, but **no `code` field**. Pydantic's default extra-field handling drops it.
6. `_apply_stage_result` does not also retain this RunState-owned field as a raw graph output. `_public_result` consequently serializes the typed payload that already lost `code`.
7. The API and frontend SSE parser pass through that final payload. No error event is emitted in this refusal, so the `errorPayload.code` branch never runs. The final detector receives `undefined` for both `final_response_payload.code` and top-level `code`.
8. Integration retains `backtest_job.failure_code`, including inside the final payload's job. The conversion detector does not read it, so #543's receipt cannot activate the modal by itself.

The observation wrapper calls the original graph function unchanged and records its input and returned state. Both boundary files show `code` present immediately before validation and absent immediately afterward:

- [Production boundary](production-failure-boundary.json) and [actual browser SSE](production-third-next-day.sse)
- [Integration boundary](integration-failure-boundary.json) and [actual browser SSE](integration-third-next-day.sse)

**Causal browser control:** On the production snapshot, a separate diagnostic attempt fetched the real response and restored only `payload.final_response_payload.code = "account_conversion_required"` in its final SSE frame. The existing workspace-limit modal opened. Parsing both streams and removing that one injected field yields identical frames; all other response fields were unchanged. This control did not modify source or production.

[Control screenshot](production-code-restored-control.png), [original response](production-code-restored-control-original.sse), [amended response](production-code-restored-control-amended.sse), [counter and modal readback](production-code-restored-control-state.json).

## When the paths diverged

There are two separate historical changes; no later removal of a previously working final-response `code` was found.

- **#279, `53e812e936f10cfa778bfce5ef7e5da54204fedd`, July 27:** `/me/usage` reported the guest workspace's `guest_session` window. `available_now` derived from that window. The modal's precheck and durable admission therefore observed the same workspace allowance. [Commit](https://github.com/lagarcess/argus/commit/53e812e936f10cfa778bfce5ef7e5da54204fedd)
- **#298, `ba0aa2f665d9dbf347f2e0cb0b986a99feb54e94`, July 28:** `/me/usage` switched to visitor-day usage, returned `guest_session=null`, and derived `available_now` only from the day window. Backtest reservation still retained the workspace limit. This is the allowance response change that permits the browser to announce availability after the day resets while the workspace is already spent. [Exact change](https://github.com/lagarcess/argus/commit/ba0aa2f665d9dbf347f2e0cb0b986a99feb54e94)
- **#354, `4a6a237a26a3509aa350c37f8a862932e19d334d`, August 3:** Added authoritative server-refusal recovery, including the bridge and the frontend nested-code detector, but left the typed payload model unchanged. The bridge first appears in component commit `642d00b43db4861f48e3937c52e0de24b6c73c17`, “fix(guest): recover quota rejection transport.” A local probe against #354's own archived source reproduces the drop at `_patched_run_state`; this fallback was already incomplete when introduced. [PR #354 commit](https://github.com/lagarcess/argus/commit/4a6a237a26a3509aa350c37f8a862932e19d334d), [component commit](https://github.com/lagarcess/argus/commit/642d00b43db4861f48e3937c52e0de24b6c73c17), [historical probe](pr354-shape.json)

The state validation mechanism predates guest conversion: it exists in #80 (`091b2265924c858e060a5304e8bfebfaf0ecd1c0`, May 7). It was not a later payload-shape regression introduced after #354.

The earlier successful browser proof is consistent with these results. #354's `seedGuestSimulationExhaustionFixture` set both workspace usage and the **current visitor-day** counter to 2/2. Its preflight clicked Run and asserted the daily-limit modal. That takes the client precheck route and does not exercise the authoritative refusal transport. Its backend test asserted `execute_stage(...).patch`, before graph state validation. This investigation crosses that missing boundary.

This also explains the DOCN chronology: the reported usage was charged on September 3, and the failing click occurred on September 4. The daily precheck can be available while the unchanged guest workspace counter remains 2/2. No collision or change to the two-run limit is needed.

## Scope of the other-detector check

A bounded scan of the frontend found one detector consuming `final_response_payload.code`: guest simulation conversion in `ChatInterface.tsx`. Both code-producing helpers emit only `account_conversion_required` into this field. The other observed recovery readers consume separate top-level `recovery`, clarification metadata, or `backtest_job.failure_code`; those are not nested members filtered by this model. This finding does not establish a repository-wide absence of contract drift.

The frontend's declared `ChatFinalPayload` also omits `final_response_payload`; the detector reaches it through a `Record<string, unknown>` cast. That is another reason the missing backend field was not caught as a shared type-contract error. It does not itself drop runtime JSON.

## Reproduction boundaries and evidence

These are **local source-exact reproductions**, not hosted deployment acceptance or an optimized Next production-build canary. Git archives of both requested SHAs supplied the frontend and backend source; Python, TS, TSX, and JSON files were compared back to their Git objects with zero changes. The Next frontend ran using `next dev --webpack`, Chromium used a 1440×1000 viewport, and the Python dependency runtime was shared between snapshots. Versions and flags are recorded in [manifest.json](manifest.json).

The harness substituted local guest authentication and prepared confirmation artifacts. Each Run click used the unchanged frontend → API router → LangGraph → execute stage → SupabaseGateway → real PostgreSQL admission path → runtime projection → API SSE → frontend parser/detector. There were no mocked SSE frames in the reproductions. The separate code-restoration control is explicitly labeled above.

The first two backtests used the real engine with `synthetic_unit_fixture` market data and persisted completed results. They were not live market-data accuracy checks or paid model runs. Runtime explanation used its provider-unavailable fallback. Workflow dispatch was disabled so those admitted runs could execute locally; both tested refusal paths return from the shared admission owner before dispatch. The LangGraph checkpointer was local memory; product records used disposable Supabase PostgreSQL 17.6 and PostgREST v14.14 with integration migrations. The only migration difference between the two SHAs is `20260903000000_claim_research_usage.sql`; the backtest-admission and guest Start over SQL definitions are unchanged.

After completing the first two runs and observing the same-day modal, the harness moved only the disposable visitor-day row to the previous UTC day to simulate rollover. It then invoked the real `replace_guest_conversation` SQL function. This left zero jobs/runs and the workspace counter at 2/2. A fresh confirmation then reached the authoritative refusal. No quotas were changed or fabricated to obtain the first two completed runs.

The `*-state.json` files record request bodies, allowance responses, database counts, modal text, and browser errors. The four `*-run1.sse` / `*-run2.sse` files retain successful Run responses. Both next-day browser captures reported zero page errors. The local default-off memory-availability probe returned its expected 403 and did not affect the run path.

All browser contexts closed. Both disposable guest owners were deleted, local frontend/API services stopped, and the PostgreSQL/PostgREST containers stopped and removed. Product source and production state remain unchanged.

The [harness directory](harness/) preserves the investigation scripts. Their staging paths assume repository-root execution with copies under `temp/docn-conversion/` and the exact Git archives under `integration/`, `production/`, and `pr354/`. Loopback ports: PostgreSQL 55482, PostgREST 55481, Argus API 55479, Next 55480. `migrate.py` expects disposable container `argus-docn-conversion-pg`; it is restricted by its fixed loopback DSN. `server.py` accepts the archive path and trace-output path. `browser.cjs` accepts an evidence label and optional `restore-code` control mode. `history_probe.py` accepts the #354 archive path.

**Disposition:** preserve #543's durable-receipt behavior. Its promotion improves diagnosis and explanation but does not repair conversion recovery. #542 must not be represented as covering this case until the conversion contract survives the graph-to-browser path. No fix or deployment was performed in this report-only follow-up.
