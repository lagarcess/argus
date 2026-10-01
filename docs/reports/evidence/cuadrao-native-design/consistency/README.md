# Cuadrao consistency checkpoint

Source: `53285d5957f11abc6fe7200717412fafa29207db` (October 1, 2026).
Scope: native design preview only. No connected root/session, financial contracts,
provider, deployment or production changes. The [living guide](../../../../../.agent/designs/cuadrao/DESIGN.md)
owns shared conventions; future work remains in the main execution board.

## Delivered

- Shared serif heading, rounded amount and native supporting-text roles across
  Home, Accounts, Plan, Chat and supporting destinations. Profile keeps its paused
  native hierarchy; navigation and identity text remain deliberate exceptions.
- One native money editor owns grouping, caret preservation, currency precision,
  rejection, blur formatting and adaptive positive-input color for Accounts and
  Plan. Plan creation, groups, custom splits, repayment and exact inputs use it.
- New plan/group amounts start empty. Explicit sample plans and values derived
  from an existing record remain populated. Currency immutability is preserved.
- Native reference gallery uses the real components, Spanish/English, light/dark,
  large text, editable and error states. Hold Home's wordmark → Guía visual.
  Appearance uses the existing preview owner and restores on gallery dismissal.

## Verification

- 58 Plan preview checks and 45 group preview checks passed at the source commit.
- Existing temporary-chat/voice preview checks passed; only typography changed
  in their UI. No live provider or microphone was used.
- Five focused native tests passed: blank creation and money error recovery,
  gallery shared behavior, all five surfaces, fixed EUR personal-plan editing,
  USD group/expense/repayment flow. See `focused-tests.json`.
- Visual review caught the gallery appearance being overridden by the app root.
  The final source fixes it through the existing appearance owner. The gallery
  and full Spanish group/custom-split journey then passed (2/2), see
  `final-delta-tests.json`. Final dark/large screenshots were visually inspected.
- Earlier surface/amount images are retained: the final gallery-only appearance
  change does not affect those surfaces. `images.json` identifies captures.
- Simulator and signed iPhone builds passed. Modularity budget and diff whitespace
  checks passed. The diff was reviewed locally for scope, shared ownership and
  hidden-field validation. No separate independent-review or CI claim is made.

The first test invocation unintentionally selected the full suite, timed out at
its tool boundary and was interrupted after the affected journeys. It is not a
full-suite pass. Its gallery-language failure was fixed; only the successful
focused reruns are used for acceptance here.

The previously tracked, unlocated `Invalid frame dimension (negative or non-finite)`
warning still appears during keyboard journeys. It is not claimed resolved.
No new clipping was observed in these captures. VoiceOver and physical gesture
acceptance are not claimed by automated screenshots.

## Phone handoff

See `phone.json` for signed build, install and launch outcomes. Installation uses
existing `local.cuadrao.design.47R3855RTJ` and preserves preview records. Automated
launch confirmation is not a claim of physical touch testing by the founder.

## Home chart

Recommended as a follow-up, recorded once under C05/C03 in the main roadmap.
The inspected Monzo/bunq references support a compact month view with a clear
recorded/estimated distinction. Home currently includes assets and debts in its
recorded position; a forecast must not silently replace that meaning. No Home
chart is included and no final chart direction is declared founder-approved.
