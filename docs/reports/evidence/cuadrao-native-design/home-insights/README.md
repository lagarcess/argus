# Quiet Home and immersive insights

October 1, 2026. UI-only native design preview.

Source: `2c5cf23bbaed77d19c07fa9ead3bccb906be342c`.
The previous source `ffd23411` passed all three focused native journeys. The final
change fixes only distribution face geometry; both affected journeys were rerun
at `2c5cf23b`, passing without warnings. Home scope/tap/scrub evidence is retained
from the parent because its implementation and test were unchanged. The later
evidence/documentation commit does not change the tested application source.

## Verified

- Quiet Home has available rolling windows, expand, tap/hold inspection and reset;
  Personal/Hogar retain distinct balances. No Home perspective switch or sample copy.
- Full-screen insights: previous-period swipe, hold-and-drag without paging,
  return to current period, no future navigation and annual view.
- Whole distribution, savings expansion, Todo reset and checking segment tap.
  Native accessibility exposes the segments as named buttons.
- English dark mode with larger text: scrollable category access and dismissal.
- 26 model checks: debt signs, ownership shares, unknown/partial balances, scope,
  rolling availability, calendar bounds, real comparison baseline and no fabricated
  history for account/currency/kind changes.
- Screenshots visually reviewed. The narrow cash segment retains its proportional
  front face; other segments become outlines when a category is selected.

## Evidence

`screenshots.json` records source and test per image. Native tests:
`CuadraoHomeChartUITests`, latest result bundle
`test_sim_2026-10-01T19-52-19-342Z_pid473_cff5646d.xcresult` (2/2),
preceding full pass `test_sim_2026-10-01T19-49-58-918Z_pid473_54ae29d5.xcresult` (3/3).
Simulator: exclusive Cuadrao design device `8AFB6084-8918-416E-9164-E21061306BEC`.

## Limits

Balances and history are explicit preview fixtures. No backend, provider, telemetry
or canonical financial-history contract changed. Reduce Motion uses opacity
without segment translation; device VoiceOver and Reduce Motion walkthroughs have
not been performed. Empty/partial/debt behavior has model/code coverage, not a full
native fixture matrix. The phone handoff confirms build/install/launch separately;
simulator gesture checks are not claimed as physical-device gesture acceptance.
Future connected work and any beta chart experiment remain in the main roadmap.

## Phone handoff

iPhone 15 build and installation succeeded (`local.cuadrao.design.47R3855RTJ`,
installation sequence 3380). The first wireless installation attempt failed with
CoreDevice 3002; one retry succeeded. Launch also succeeded after one remote-process connection retry.
See `phone-handoff.json` for the separate build/install/launch results.
