# Distribution typography correction

October 1, 2026. Source `9e64509ffe6743db0f6d7243103991bc55c9b3af`.

Restore the original compact native system category labels (`supporting`). Money
and percentages use `rowAmount`; account names and quiet counts retain their
existing system styles. The WIP guide now distinguishes financial rows from
serif content-section headings. Layout and behavior code are unchanged.

Both existing native journeys passed at this source: history/distribution and
English dark mode with accessibility-size text. Result bundle:
`test_sim_2026-10-01T20-01-37-275Z_pid473_6dd8b8b6.xcresult` (2 passed, no warnings).
The attached simulator screenshots were visually reviewed. Physical-device build
succeeded. Installation/launch status is recorded below. No production integration.

Physical iPhone 15 installation succeeded (sequence 3388) and launch succeeded
for `local.cuadrao.design.47R3855RTJ`. Gesture acceptance was on the designated
simulator; phone build/install/launch are separate handoff evidence.
