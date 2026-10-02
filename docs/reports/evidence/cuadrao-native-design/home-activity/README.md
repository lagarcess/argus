# Home activity and header polish

UI-only Cuadrao preview, October 1, 2026. No connected finance/provider changes.

## Delivered

- Greeting without date; shared plain space-creation plus.
- Household avatar entry above the amount, derived from accepted local membership.
- Period title left and Balance / Activity right above the amount. Week/month use a date
  range; year uses the year. One row below owns period and chart controls.
- No visible paging arrows or Back to today. Bounded swipes and
  VoiceOver period actions remain, including empty history.
- Expense-category stacks for week/month; monthly stacks for year. Adaptive
  native axis ticks keep period context at the axis, including larger English text.
- Period expense distribution and expandable records use the same totals/categories.
- Categories share Plan's palette and Home's outline vector family/soft icon tiles.
- Sparse, varied fixtures cover a complete previous year: bills, quiet days and
  occasional larger purchases, without repeated daily rainbow stacks. Account and
  expanded category histories render lazily; account rows are newest-first.
- Historical asset allocation uses dated account observations, preserving account drill-down.

## Verification

Six native Home journeys passed in the final layout/data batch:
compact Home/household, history/distribution paging, account round-trip, large English
asset distribution, expense period/distribution, and large English expense chart.
Full batch: test_sim_2026-10-02T01-44-57-285Z_pid473_7221a0b6.xcresult (6 passed).
After the category art change, both affected Activity journeys passed again:
test_sim_2026-10-02T01-48-37-688Z_pid473_2f300c6a.xcresult (2 passed).

37 deterministic checks passed for balance ownership, historical snapshots, expense
scope/currency/income exclusions, bucket reconciliation, calendar boundaries and
past-year monthly coverage with quiet days. Modularity budget and git diff whitespace
checks passed. The earlier oversized-fixture test was stopped after it exposed eager
account-history rendering; it is superseded by the complete passing batch above.
Account round-trip returned to approximately 23 seconds after lazy history rendering.

Screenshots are retained here; final checkpoint source was revalidated against their
relevant unchanged paths. Activity screenshots use the final category artwork.
Signed iPhone build 3408 includes the period header, natural fixtures and artwork.
Installed on Sr.Garces i15 (iOS 27.0.1), sequence 2128; device launch confirmed.
Simulator verification used only 8AFB6084-8918-416E-9164-E21061306BEC.

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
