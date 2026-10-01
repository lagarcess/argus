# Cuadrao native design

Living baseline, October 1, 2026. The founder approved consolidating the native
preview's typography, money editing and reference gallery before receipt splitting.
This guide owns Cuadrao's shared visual/interaction conventions. It does not change
production Argus web styling, financial contracts, providers or the connected app.
The [main roadmap](../../../docs/specs/argus-execution-board.md#cuadrao-design-dispositions)
continues to own unfinished work and delivery status. Existing approved account,
chat, voice and Plan behavior is preserved unless this guide explicitly revises it.

## Character and hierarchy

Cuadrao is warm, clear and personal. Home offers a calm first glance; Plan makes
exploration inviting; Chat leaves space for conversation. Shared typography,
amount behavior and controls make these feel related without identical layouts.
Art belongs where it identifies an intention. It should not compete with a money
value, make a row hard to scan or imply that a prediction is certain.

## Implementation owners

| Shared decision | Single code owner | Usage |
| --- | --- | --- |
| Typography roles | [CuadraoTypography.swift](../../../ios/ArgusFoundation/Cuadrao/CuadraoTypography.swift) | Use named roles for expressive headings and amounts. Native navigation titles, text bodies and system controls retain their semantic text styles. |
| Adaptive palette | [WelcomePalette](../../../ios/ArgusFoundation/Cuadrao/CuadraoCanvas.swift) | Pine, sage, background, surface, ink, borders and positive input text. The historical type name remains; do not create a competing Cuadrao palette. |
| Money parsing and caret behavior | [CanvasDecimalInput.swift](../../../ios/ArgusFoundation/Cuadrao/CanvasDecimalInput.swift) | Accounts and Plan use this same native text editor. |
| Currency precision, formatting and limits | [CanvasMoney.swift](../../../ios/ArgusFoundation/Cuadrao/CanvasMoney.swift) | Derive preview limits and formatting here; currency selection/immutability retains its plan/group owner. |
| Numeric preview bridge | [CanvasMoneyValueInput.swift](../../../ios/ArgusFoundation/Cuadrao/CanvasMoneyValueInput.swift) | Adapts existing numeric preview models to decimal editing text; it is not a new financial store. |
| Plan amount composition | [PlanAmountInput.swift](../../../ios/ArgusFoundation/Cuadrao/Planning/PlanAmountInput.swift) | Currency, rounded amount, focus underline and inline error. Accounts keeps its approved bordered, right-aligned composition around the same editor. |
| Choice labels and add shortcuts | [CuadraoChoiceControls.swift](../../../ios/ArgusFoundation/Cuadrao/CuadraoChoiceControls.swift) | Shared value/caret, selected menu option, fixed code and section plus. |
| Expanded chart controls | [CuadraoChartControls.swift](../../../ios/ArgusFoundation/Cuadrao/CuadraoChartControls.swift) | Icon view choice and localized period choice, including selected accessibility state. |
| Account management | [CuadraoAccountsCollection.swift](../../../ios/ArgusFoundation/Cuadrao/CuadraoAccountsCollection.swift) | Native ordering and archive recovery over the existing shared account model. |
| Reference gallery | [CuadraoDesignGallery.swift](../../../ios/ArgusFoundation/Cuadrao/CuadraoDesignGallery.swift) | Uses real shared components. Access from a hold on Home's greeting → Guía visual / Visual guide, or launch with `--design-gallery`. Preview-only. |

## Typography

| Role | Treatment | Examples |
| --- | --- | --- |
| `screen` | Native large-title serif | Plan heading, chat landing |
| `feature` | Native title serif | Important local headline |
| `section` | Native title2 serif | Accounts, plans and content sections |
| `body`, `supporting`, `caption` | Native readable system text | Instructions, metadata and controls |
| `amount`, `secondaryAmount` | Rounded medium numerals, stable digit widths | Summary money and editable money |
| `rowAmount` | Compact rounded numerals, stable digit widths | Financial rows |
| `action` | Native body medium | Primary action labels |

Expandable financial rows are controls, not content-section headings. Use
`supporting` system text for distribution category and account names, `caption`
for account counts, and `rowAmount` for both money and percentages. Keep serif
`section` for actual content sections such as Cuentas or Próximamente.

Type scales with Dynamic Type. Long amounts may reduce to fit their bounded field;
large-text content must otherwise wrap or scroll. Native navigation titles,
profile identity, avatars, icons and the Cuadrao wordmark are intentional distinct
roles, not candidates for a blanket serif replacement. Profile hierarchy remains
at the founder's paused checkpoint; sharing typography does not approve a redesign.

## Money editing

Typing means whole units first, with optional decimal places. Group thousands
while editing and preserve selection/caret, including deletion near separators.
Pad the currency's decimal places on blur. Reject letters, malformed pasted
grouping, excess precision and out-of-range values without silently rounding an
entered amount. Show the inline error and prevent saving while it remains.
A valid subsequent edit clears that field's error; editing another field does not.

Empty is an empty input with a quiet formatted-zero placeholder. Positive entered
amounts use the shared adaptive teal. Optional account balance still distinguishes
unknown from zero. Required plan amounts must be entered before creation; optional
starting progress can remain zero. New personal plans and groups no longer inherit
fictional target or monthly-contribution defaults. Named examples keep their sample
values. Existing records and repayment amounts derived from an actual preview
balance can still populate their editors; those are not arbitrary suggestions.

Keep primary and secondary amount hierarchy, currency choice at creation and
fixed currency after creation. Do not change financial storage or add exchange
rates as a typography/input change. A proposed future recommendation must disclose
its basis and be explicitly applied; no such recommendation is implemented here.

## Components, spacing and motion

Use existing native buttons, sheets, rows and context menus. Preserve approved
icons and icon-only navigation. Major content uses the existing 24-point page
inset, with 8/12/16/24 spacing where appropriate; these are layout conventions,
not a mandate to flatten artwork, chat composition or native Form insets.
Keep touch targets at least 44 points. Show error text alongside semantic color.
The money editor retains its short grouping fade and respects Reduce Motion.
Scroll-edge materials belong behind persistent chrome, never across interactive
content. Surface-specific gestures retain their existing meanings.

### Locked selector language — October 1, 2026

Single-choice selectors show the current value and a downward chevron, with a
checkmark on the selected option. Apply this grammar to space and currency choices,
where a choice is necessary. Reserve the sliders/filter icon for controls that open
multiple filter dimensions. Align typography, caret weight and accessible touch
targets across equivalent controls while retaining each surface's composition.
Short choice lists can use native menus; long currency catalogs use a searchable
sheet. Fixed currency is a static code without a chevron, with a lock where useful.
Home's currency choice filters a view; plan/group creation chooses a currency that
stays fixed afterward. Shared presentation does not introduce conversion or change
those ownership rules. Delivery status remains in the main roadmap.

## Review and evolution

The gallery offers Spanish/English, light/dark and large-text controls. It contains
headings, amounts, a row, a disabled action, working Account/Plan input fields,
and the real shared choice, add and chart controls.
Use it to compare states, then verify the actual surfaces: isolated components do
not prove keyboard, scroll or navigation behavior. The gallery does not post data.

For a new feature, reuse the shared roles/components first. When a new pattern is
necessary, mark it experimental in its assigned work; promote it here after review
and migrate equivalent usages together. Update the component owner rather than
copying a style or parser. Preserve each surface's useful personality. Tests should
exercise meaningful behavior and navigation, not freeze every styling literal.
Future chart, receipt, provider and connected-delivery work stays in the roadmap.

## Locked Plan hierarchy — October 1, 2026

Share Home's interaction language while preserving Plan's hierarchy. Plan's main
distinction is Para ti / En grupo. The founder's subsequent whole-surface review
supersedes the separate Tus planes space filter and standalone forecast-month row.

Keep one space choice attached to the forecast, alongside Tu mes / Your month,
not beside the page title. Dates remain explicit within the chart/readout; do not
repeat October above it. Hide the choice when only one compatible space exists.
Tus planes shows all active personal plans with space metadata on each card, without
Todos or a second space filter. A forecast-space change never sets a new plan's
space: creation starts with an explicit editable Personal choice.

Keep the header's primary plus, whose action and accessible name follow Para ti /
En grupo. Remove the header ellipsis: preview controls belong in the title hold
menu, while each collection has a quiet archived-items destination for its own
records, reachable after all items are archived. Keep a welcoming creation action
in empty states; remove the duplicate group-create action from populated lists.
Cards use the shared collection gestures below; detail retains visible editing,
renaming and archive actions. Group People owns invitations and member management.
Tapping the avatar stack opens People. Only the local organizer scenario exposes
member management; removal is reviewed, blocks outstanding balances, and retains
historical expenses/contributions. Connected permissions remain roadmap work.

Same action, same behavior; different purpose, different composition. Shared
money behavior, typography, icons, selectors, gestures and return paths provide
consistency. Plan retains its illustration, exploration and personal language. The forecast
playground entry is a quiet “Explorar escenarios / Explore scenarios” link beneath
the forecast, rather than an attention-seeking headline or primary action.
Implementation status and future work live in the
[main roadmap](../../../docs/specs/argus-execution-board.md#cuadrao-consistency-pass-and-home-chart-follow-up).

## Home account and activity shortcuts

Cuentas / Accounts and Movimientos / Activity share the same trailing plain plus.
Home keeps quick creation and row gestures; no accounts-header ellipsis or redundant
configuration cluster. Account rows use the same collection gestures as Plan.
Tapping the Accounts heading opens its management surface, where visible reorder
and archived-account recovery remain discoverable. The entry remains available
when all accounts are archived. Account detail retains visible owner actions;
Home's shortcut does not become the only way to manage a record.

## Collection gestures

`CuadraoOrderedCollection` owns the shared interaction across Home account rows,
personal plans and group cards. Tap opens detail; swipe right reveals Edit
(including rename); swipe left reveals Archive. Neither swipe executes on a full
swipe. Hold and drag reorders directly in place, without a context menu or an
ordering tray. Sheets are for actual editing, invitation and review flows.

Use native iOS 27 reorder/swipe containers. iOS 17–26 retain native drag/drop and
visible Edit/Archive alternatives; the deployment minimum remains unchanged.
Accessibility actions include Edit, Archive, Move up and Move down. The existing
account management destination remains an alternative with visible order handles.
`CuadraoCollectionOrder` applies only the visible IDs without moving hidden or
archived records. Preview owners persist plan/group order and fixture account order;
connected viewer-specific order is a future contract, not a shared financial edit.

## Home balance chart

Home keeps a compact recorded-position chart, with the same debt signs and asset
ownership shares as its amount. `CanvasBalanceHistory` owns that projection;
`CuadraoHomeOverview` owns presentation. Select currencies separately, never add
or convert them. Personal/Hogar retain the existing account-scope owner.

Tap to retain one observed date/value, hold and drag to inspect, and use Hoy/Today
to return to the current balance. The native chart leaves regular vertical
scrolling available. Keep the pine line, subtle fill and readable range labels.
Keep test/sample provenance in preview tooling and evidence, not in Home content. Missing history gets an empty state; no flat
line, inferred pre-account balances or forecast is invented. A new account or
currency/kind/share change cannot silently borrow old example observations.

The existing Próximamente / Upcoming link opens Plan as a separate surface; it does not imply its sample
forecast is computed from Home's accounts. Connected history/forecast ownership
and scope-preserving navigation remain in the main roadmap.

### Home welcome and history perspectives

Home uses a compact, static native-system greeting: Hola / Hello plus Profile's
preferred name, or just the greeting if missing. The shared preview profile state
lives in `CuadraoHomeCanvas`; Profile edits and Home read the same value. A localized
date sits above it. Space switching changes the financial scope, not the welcome.
The greeting's context menu retains the preview gallery/reset tools.

### Locked Home and expanded insights direction — October 1, 2026

This founder-approved direction supersedes the presentation at checkpoint
`f989d2ec`.
Implementation status and all future work belong only to the
[main roadmap](../../../docs/specs/argus-execution-board.md#cuadrao-consistency-pass-and-home-chart-follow-up).

**Quiet Home:** compact welcome, existing space selector, amount, one history line,
and short available-history ranges (for example 1 mes / 1 month). Only offer ranges
supported by the person's recorded history. Keep a subtle, accessible expand icon.
Do not show Evolución / Distribución controls, insight paragraphs or test/sample
copy on Home. Genuine unknown/partial values remain distinguishable from zero;
removing preview disclosures does not authorize invented financial facts.

**Expanded insights:** opening the chart creates the immersive detail surface.
Evolución / Distribución live here. Evolución uses Semana / Mes / Año (Week / Month /
Year), starts at the latest period, and allows swipe right to go back and swipe
left toward the present, stopping at today. Its one short takeaway explains an
observed change with a clear basis. Spending comparisons require equivalent elapsed
periods; a balance change must not be described as earnings, spending or investment
return. Inspection and period paging must coexist with vertical scrolling and
accessible alternatives. The metric remains recorded net position unless separately
changed; Apple spending visuals do not redefine that metric.

**Locked control refinement:** place the compact line-chart / stacked-bar icon
switch beside the hero amount, with clear selected state and localized accessible
names. Above the history chart, size Semana / Mes / Año to localized labels instead
of stretching the selector across the screen. Preserve 44-point touch targets and
allow layout to adapt for larger text rather than truncating labels or money.
Show a subtle neighboring-period edge only when that period exists, with explicit
previous/next controls beside the period title as an accessible alternative. Stop
at the oldest available period and the present; do not tease unavailable pages.
Keep chart inspection distinct from paging and preserve vertical scrolling.

Period selection and historical paging apply only to Evolución. Distribución shows
current positive assets, labeled Activos · Hoy / Assets · Today: remove period controls and date paging there and make its current
scope clear. Switching views preserves Evolución's chosen period for the return,
but never applies that past date to today's distribution or leaves a stale date
label attached to it. Do not imply historical allocation support. These controls
belong only in expanded insights; the compact Home entry remains quiet.

**Distribución: decomposable bar, category rows, account detail.** The bar shows the
whole positive asset distribution. Selecting a category emphasizes its segment;
other segments recede or separate while preserving context. Matching expandable
rows reveal the category's accounts, keeping amounts readable independently of the
visual. Example: Todo → Ahorros → Mi tranquilidad / Fondo de la casa. Tiny segments
remain reachable through rows. Tapping the selected category again or Todo restores
the whole. Keep category colors stable across the bar, rows and drill-down.
Category rows use a down/up chevron to expand or collapse. Account rows use a
right chevron and push the existing account detail within the insights navigation
stack. Back preserves the selected category and scroll position. Detail actions
reuse `CuadraoAccountModal` and the shared account model; edits are reflected on
return. Do not dismiss insights and strand the person at the Accounts root.

Subtle depth is approved as a visual direction, with proportional front-facing
widths; depth must not distort the financial comparison. The proposed gentle
separation/reassembly is our interaction design, not a claim that reference
screenshots prove that animation. Use a simple fade with Reduce Motion. Account
percentages retain the same positive-asset-total denominator through drill-down;
any later within-category percentage needs an explicit denominator label. Debt and
other negative balances stay separate. One currency at a time, with no conversion.
The user-facing name stays Distribución / Breakdown, not Decomposition.

The bar is the baseline. A donut remains only a future experiment candidate with
the same rows, values and interactions; no chart-type chooser is required on Home.

References: [Wealthsimple history](https://mobbin.com/screens/667bf371-6e73-42f5-b179-574e62d9b64b),
[Apple Wallet periods](https://mobbin.com/screens/82a32fee-bf5f-4c39-b4b8-0e002de68d4c),
[Apple comparison and paging](https://support.apple.com/en-us/102329),
[Public allocation](https://mobbin.com/screens/07c1ff8c-f0da-4bf0-919a-d21b2ac5ff43),
[Origin disclosure](https://mobbin.com/screens/7edb40e1-bbbe-4c1a-9916-f10f943d7685).
Founder-supplied decomposition screenshots are retained with this decision's
[reference evidence](../../../docs/reports/evidence/cuadrao-native-design/home-distribution-reference/README.md). They motivate the hierarchy and subtle depth; they are not
Cuadrao implementation or acceptance evidence.
