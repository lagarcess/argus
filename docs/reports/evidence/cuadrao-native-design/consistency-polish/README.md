# Cuadrao Home and Plan consistency polish

October 1, 2026. UI-only source: `3b04bc2307a6bb08603082c34fb6cbbaa4062dd0`.
Main polish: `034ae234`; final account-row correction: `3b04bc23`.
The tested application and test sources were committed unchanged. This evidence
and roadmap checkpoint changes documentation only, retaining that exact source.

## Verified journeys

Main polish run: **9 passed, 0 failed**, on design simulator
`8AFB6084-8918-416E-9164-E21061306BEC` (iPhone 18 Pro).
Result: `test_sim_2026-10-01T21-18-03-430Z_pid473_6c745648.xcresult`.
No warnings were reported in this batch.

- Home balance, history selection and Personal/Household switching.
- Swipe historical periods; inspect without paging; stop at oldest/current bounds.
- Switch to current distribution without historical controls; return to the same period.
- Distribution category/account navigation, rename, record cancellation and preserved scroll.
- English dark appearance with accessibility-size text, including Plan controls.
- Account hold → reorder → actual row movement → detail → archive → restore.
- Archive every active Household account, reenter through Home, and restore one.
- Search the Accounts currency catalog and select EUR.
- Change forecast scope without changing a new plan's default; explicit plan-space choice still works.

The earlier supporting batch passed **7/7**, including the unchanged personal EUR
creation/fixed-currency and shared USD split/repayment journeys, plus forecast/goal
exploration. Result: `test_sim_2026-10-01T21-10-45-554Z_pid473_265bbc91.xcresult`.
Four chart cases were then repeated in the final batch after the neighboring-card
edge adjustment; currency/forecast source did not change. The two currency tests
emitted an `Invalid frame dimension` runtime warning when opening the name-field
keyboard. They completed successfully; the captured currency/amount layouts were
reviewed without visible clipping. That diagnostic is not claimed resolved here.

`git diff --check` and `scripts/check_modularity_budget.py` passed for the design
checkout. This is a design checkpoint, not an integration/release-readiness audit.
No backend, provider, financial contract, analytics or production work was added.

The final visual review caught long names crowding money in the native account
list. The shared row now gives names a flexible column and uses a vertical amount
layout at accessibility sizes. After this correction, hold/reorder/archive/restore
and large-English account management passed **2/2** at the final source, with no
warnings (`test_sim_2026-10-01T21-25-24-768Z_pid473_2ae25471.xcresult`). Normal and
large-text row screenshots were inspected. The unaffected chart, currency and
Plan evidence is retained; no state/model/navigation logic changed in this follow-up.

## Visual evidence

Selected native screenshots are committed alongside this file; `screenshots.json`
maps each to its test and source. Images are JPEG exports of XCTest captures.
Reviewed the historical readout and neighboring-card edges, normal distribution,
dark/larger text, Plan hierarchy, matching Home shortcuts, reorder/archive states
and currency input presentation. Prior large amounts/fixed currency remain intact.

## Physical iPhone handoff

The same application source built successfully for iPhone 15 and was installed
as `local.cuadrao.design.47R3855RTJ`, bundle version **3402**, installation sequence
**3412**. Launch succeeded. Gesture acceptance above is simulator evidence; this
records physical installation/launch, not an unobserved manual phone review.

## Research used

- [Monzo pot flow](https://mobbin.com/flows/74df8eb8-a70b-4d66-9778-62416d46c798): quick creation separated from management.
- [Revolut choice menu](https://mobbin.com/screens/703e98ac-e7a9-41c0-9eb7-fed3f38cac7d): current value and selected choice.
- [Wise currency search](https://mobbin.com/screens/aaed207b-aeb2-490c-b8a0-e2fb6d58320f): code/name lookup for a long catalog.
- [Origin chart controls](https://mobbin.com/screens/369e7d56-50a2-4db5-9b8a-535479ed77fc), [Wallet periods](https://mobbin.com/screens/82a32fee-bf5f-4c39-b4b8-0e002de68d4c), [Lloyds period navigation](https://mobbin.com/screens/f06acbc4-ffaa-4b40-8e2c-464e80f3e53c): compact choice and discoverable navigation.

References informed our adaptation; screenshots do not establish usability scores
or prove animations. Shared rules live in the Cuadrao design guide; all remaining
connected work and future dispositions stay in the main execution board.
