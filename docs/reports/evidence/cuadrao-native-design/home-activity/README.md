# Home activity and header polish

UI-only Cuadrao preview, October 1, 2026. No connected finance/provider changes.

## Delivered

- Greeting without date; shared plain space-creation plus.
- Household avatar entry above the amount, derived from accepted local membership.
- Balance / Activity selection above the amount. One row owns period and chart controls.
- No detail date heading, visible paging arrows, or Back to today. Bounded swipes and
  VoiceOver period actions remain, including empty history.
- Daily expense-category stacks for week/month; monthly stacks for year. Adaptive
  native axis ticks keep period context at the axis, including larger English text.
- Period expense distribution and expandable records use the same totals/categories.
- Historical asset allocation uses dated account observations, preserving account drill-down.

## Verification

Six distinct native Home journeys passed across the final verification batches:
compact Home/household, history/distribution paging, account round-trip, large English
asset distribution, expense period/distribution, and large English expense chart.
The complete five-case existing+expense batch passed before the final empty-period
and axis refinements; affected history and expense journeys were rerun afterward.
Final expense batch: test_sim_2026-10-02T01-34-19-406Z_pid473_f306b996.xcresult.
Final history batch: test_sim_2026-10-02T01-31-49-792Z_pid473_da2c4fca.xcresult.
Retained unaffected Home/account batch: test_sim_2026-10-02T01-29-24-579Z_pid473_aa332bbc.xcresult.

34 deterministic checks passed for balance ownership, historical snapshots, expense
scope/currency/income exclusions, bucket reconciliation and calendar boundaries.
Modularity budget and git diff whitespace checks passed.
Screenshots are retained here; final checkpoint source was revalidated against their
relevant unchanged paths. Activity axis screenshots use the final source.

Signed iPhone build 3406 installed on Sr.Garces i15, iOS 27.0.1, installation sequence
2112; device launch confirmed. Simulator verification used only 8AFB6084-8918-416E-9164-E21061306BEC.

## Boundaries

Preview fixtures are explicitly synthetic, supplied through the existing activity
owner. The household preview currently supports owner plus one accepted companion;
pending invitations do not create avatars. Connected multi-member identity, category
coverage and financial history remain in the main execution board, not this evidence.

## References inspected

[Apple Wallet category stacks and period controls](https://mobbin.com/screens/82a32fee-bf5f-4c39-b4b8-0e002de68d4c)
and [Apple spending activity](https://support.apple.com/en-ca/102329) informed the
expense breakdown. Airbnb wishlist searches did not expose a better avatar pattern;
we retained Cuadrao's existing avatar stack rather than claiming a researched clone.
