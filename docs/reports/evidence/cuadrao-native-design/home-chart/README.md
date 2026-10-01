# Home chart UI checkpoint

Source: `5c0b6b6aa3d92d2e04030f91f9287aecea881696`.
Native preview only; no production, service, persistence or financial API changes.

Home shows recorded position for the current account scope, with one currency at
a time. The amount and line derive from `CanvasBalanceHistory`. Debts subtract;
owned asset shares apply; unknown balances remain partial. Explicit sample
observations are labeled. New accounts with no history show an empty state.
Changes to currency, kind or ownership share cannot relabel sample history.

Tap retains a date/value. Hold and drag scrubs. Hoy/Today resets. Native Chart
accessibility exposes dated values; VoiceOver audio-graph playback is not claimed
manually tested. Ordinary vertical scrolling is retained. The link opens Plan;
it does not claim Home-derived forecast values or matched currency/scope routing.

## Evidence

- 15 pure projection checks passed: signs/shares, unknown/partial/empty, endpoint
  consistency, chronology, no forecast, new-account and currency/kind boundaries,
  negative balances and single-observation behavior.
- Two native tests passed: Spanish inspection/reset/space switching/Plan return,
  and English dark mode/large text/navigation. Additional hold-and-drag plus
  settled household-width/return assertions passed in the focused rerun.
- Final screenshots were visually inspected. A capture taken during the Household
  transition was replaced with the settled return capture. The width assertion
  passes; the settled amount and axis labels fit.
- Simulator and signed iPhone builds passed; modularity and whitespace checks
  passed. Native test runs report no warnings. Initial test attempts were corrected
  for Swift Charts accessibility container matching and bounded scroll distance;
  the initial disappearing selection led to the persistent-tap implementation.
- All app code is identical to source `5c0b6b6a`; later changes add test assertions
  and evidence only. Dark/large captures remain valid at that exact app source.
- `phone.json` records installation and launch separately. Installed preview
  identity is preserved. Physical touch approval remains with the founder.

## References and remaining work

[Monzo selected balance](https://mobbin.com/screens/25125eda-5e62-4166-9a68-9b25bcc349b6)
informed the paired date/value readout. [Apple Swift Charts interaction](https://developer.apple.com/videos/play/wwdc2023/10037/)
informed native selection/gesture composition. The pine/serif/rounded treatment
comes from Cuadrao's shared guide.

Future connected history, historical membership/valuation rules and a shared
forecast owner remain only in the [main roadmap](../../../../specs/argus-execution-board.md#cuadrao-consistency-pass-and-home-chart-follow-up).
