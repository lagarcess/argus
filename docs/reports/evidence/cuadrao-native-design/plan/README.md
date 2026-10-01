# Cuadrao Plan: native UI checkpoint

October 1, 2026. Founder-authorized **UI only**, continuing design checkpoint
`1b2005fd9b94970dc75ebf78175e4765db9fce39`. This is a native design preview, not
connected financial functionality or a release candidate. Research and its limits
are retained in [research.md](research.md).

## Try it

Open **Cuadrao Preview → Plan** (the existing calendar icon).

1. **¿Y si cambias el ritmo?** opens the month playground. Drag the spending slider
   or tap its amount for exact native entry. Read the low point, expand **¿De dónde
   sale?**, then save or reset. The overview reads the same saved assumption.
2. Open **Un finde en Samaná**, adjust the contribution, or try a 3/6/12-month
   arrival. The date and chart change together. **Aplicar a mi plan** saves;
   **Deshacer prueba** restores the saved choice. Exploration never adds savings.
3. **+** creates a goal, monthly budget, or debt plan. Name it, choose a native
   illustrated cover, set the amount and monthly contribution where applicable.
   Space and currency remain visible. Optional starting progress and fixed annual
   interest sit under **Punto de partida**. Saving opens the new plan.
4. Use a plan's menu to edit or archive. **Plan → … → Archivados → Retomar**
   restores its progress. Holding a card offers edit/archive shortcuts.
5. Filter plans by space. The forecast has its own explicitly labeled Personal /
   Hogar scope; goals from different currencies are never totaled together.
6. Plan's **…** menu offers first use and reset examples, with a confirmation.
   Exploring an example month from first use preserves any plans already created.
7. Minimize the existing voice preview and switch to Plan. Voice controls and
   navigation remain reachable; the Plan scroll area reserves their space.

Preview plans and selected spending assumptions persist locally across app
launches in `cuadrao.design.plans.v1`. Only the design model writes that key.
`--plan-reset` and `--plan-empty` are reproducible simulator launch options;
`--design-english` selects English. These options are not used for normal device
launches. Existing unrelated preview data is preserved.

## Design decisions carried forward

- The forecast leads; the surface helps explore a future rather than merely
  reporting past spending. Native Swift Charts supports reading dates and values.
  Solid is recorded sample history; dashed is a projection. Future bills/income,
  the low point, and assumptions are inspectable. Saved assumptions are labeled
  as a plan rather than presented as observed pace.
- Space is quiet context on each plan and an optional list filter. The overview
  does not repeat Home's main space-selector frame. Creating a plan makes its
  space explicit; household details reuse the existing people/invitation UI.
- Native sliders provide direct manipulation, exact amount sheets provide an
  accessible alternative, and 3/6/12-month choices reduce typing. No hidden
  gesture is required. Navigation does not move or collapse while manipulating.
- Native vector covers, serif headings, warm secondary colors, short copy and
  subtle selection/save haptics give Plan personality without scores or streaks.
  Shared light/dark colors and scroll-edge materials preserve the app's style.
- UI state owns preview calculations in one place. Chart values, completion
  dates, and contribution presets derive from `CanvasPlan`; the forecast chart,
  ending value and low point derive from `CanvasForecast`. Views do not run a
  second repayment calculation. Observed destinations read the same store.
- Recorded progress remains separate from planned contributions. A budget's
  allowance does not change its projected spending pace. New budgets with no
  activity do not invent a forecast. Completed goals stop showing a future path.
- The example month is fixed at October 12, 2026 and visibly labeled. Savings
  assume fixed monthly contributions and no returns. Debt assumes a disclosed
  fixed annual interest rate, monthly payments, no new purchases and no fees.

## Delivery boundaries at this checkpoint

Current follow-up status lives in [roadmap C02/C03/C09](../../../../specs/argus-execution-board.md#cuadrao-design-dispositions).
The following records this earlier build's boundaries, not a second current queue.

No API, database, migrations, auth, model prompt, provider integration, money
movement or production flags were changed. The separate connected Plan client,
its canonical payment records, and delivery work are untouched. The illustrative
forecast is not derived from Home's account balances. Its assumptions exclude
savings/goals and other people's private accounts; it must be replaced by the
agreed forecast contract before connecting real data. Home should then consume
that same owner, never independently calculate a forecast.

Monthly budgets here explore an allowance; transaction/category allocation and
linked payment/contribution recording remain the connected delivery lane's job.
Household permissions and contribution attribution are not implemented by this
preview. Exact target-date picking, optional personal cover photos and production
forecast uncertainty bands remain future refinements, not claims of this build.
The existing voice proposal remains its separate illustrative review flow.

## Verification

- `python3 ios/DesignPreviewTests/run_plan_preview.py`: 44 checks covering cash
  conservation, scope isolation, shared chart/date projections, invalid input,
  apply-vs-recorded progress, persistent archive/restore and cold-start continuity.
- `python3 ios/DesignPreviewTests/run_temporary_chat.py`: existing Spanish/English
  chat, temporary mode, voice and recording state checks passed.
- Five native XCTest journeys cover forecast/goal experiments, creation/edit and
  recovery, all plan kinds, household/English, large text/first use, exact input,
  dark mode and minimized voice continuity. Screenshots are exported alongside
  this report. Final source revision and device delivery receipts are recorded in
  `verification.md` after the final run.

The first archive UI run found a stale destination after restore. Giving that
navigation destination its own observed SwiftUI view fixed it; the same recovery
journey then passed. Native keyboard presentation still emits a non-finite-frame
warning during text focus; the inspected editor captures and input/save journeys
show no clipping or interaction failure. This is retained as a polish observation,
not silently counted as a clean runtime log.
