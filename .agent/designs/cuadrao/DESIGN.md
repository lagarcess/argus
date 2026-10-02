# Cuadrao native design

Approved native baseline, October 2, 2026. The founder approved consolidating the native
preview's typography, money editing and reference gallery before receipt splitting.
This guide owns Cuadrao's shared visual/interaction conventions. It does not change
production Argus web styling, financial contracts, providers or the connected app.
The [main roadmap](../../../docs/specs/argus-execution-board.md#cuadrao-design-dispositions)
continues to own unfinished work and delivery status. Existing approved account,
chat, voice and Plan behavior is preserved unless this guide explicitly revises it.

This is a reference organized by design rule, not a sequence of polish notes.
The [Argus guide](../argus/DESIGN.md) supplies the document structure; Cuadrao keeps
its native type, palette and artwork. Delivery evidence belongs in the roadmap.

## 1. Character and surface purpose

Cuadrao is warm, clear and personal. Home offers a calm first glance; Plan makes
exploration inviting; Chat leaves space for conversation. Shared typography,
amount behavior and controls make these feel related without identical layouts.
Art belongs where it identifies an intention. It should not compete with a money
value, make a row hard to scan or imply that a prediction is certain.

| Surface | Heading purpose | Treatment |
| --- | --- | --- |
| Home | Welcome: Hola / Hello plus preferred name | Compact native system greeting |
| Chat | Invite conversation | Expressive serif landing text; preserve typed opening behavior |
| Plan | Look ahead: Lo que viene / What's ahead | One serif heading with the primary plus; no repeated subtitle |
| Profile and Settings | Identify the destination | Personal identity, quiet grouped destinations and clear native titles |
| Expanded insights | Identify the selected period | Serif feature title; controls stay anchored while period evidence pages |

Tab identity does not require a second literal surface title. Keep heading/action
alignment, typography roles and touch behavior consistent. Copy, illustration and
content density can vary with purpose.

## 2. Color palette and roles

`WelcomePalette` is the only native palette owner. Read its adaptive values rather
than copying RGB literals into screens. Colors below describe roles, not a new store.

| Token | Role |
| --- | --- |
| `background`, `surface` | Page and quiet supporting surfaces; adapt to appearance |
| `ink` | Primary content; secondary system text for metadata |
| `pine`, `sage`, `overlap` | Primary emphasis, quiet selection wash and layered art |
| `moneyInput` | Legible positive entered amounts |
| `sunshine`, `clay`, `bloom` | Plan artwork and stable category accents |
| `onAccent` | Readable content on accent surfaces |
| `separator`, `border` | Quiet boundaries |

Category colors come from `CuadraoExpenseCategoryStyle`. Keep them stable in charts,
rows and drill-down. Pair color with names or symbols. A spending increase is not
an error or a moral judgment. Destructive actions retain their existing semantic
red; don't repaint them with a category accent. Artwork may use depth and gradients
without turning numeric charts into decorative data.

## 3. Typography rules

`CuadraoTypography` owns display and money roles. Default point sizes below describe
the standard Large content-size category; semantic Dynamic Type scaling remains
authoritative. Do not freeze a screen to these point sizes.

| Role | Native style / default pt | Design | Weight | Use |
| --- | --- | --- | --- | --- |
| `screen` | largeTitle / 34 | Serif | Regular | Expressive landing heading, Plan or detail name |
| `feature` | title / 28 | Serif | Regular | Period heading or a substantial local headline |
| `section` | title2 / 22 | Serif | Regular | Cuentas, Tus planes, Lo que destaca |
| `body` | body / 17 | System | Regular | Explanations and reading |
| `supporting` | subheadline / 15 | System | Regular | Financial row labels, selectors, secondary descriptions |
| `caption` | caption / 12 | System | Regular | Dates, counts and supporting metadata |
| `action` | body / 17 | System | Medium | Primary action text |
| `amount` | largeTitle / 34 | Rounded | Medium | Hero and primary editable amounts |
| `secondaryAmount` | title2 / 22 | Rounded | Medium | Secondary summary amounts |
| `rowAmount` | subheadline / 15 | Rounded | Medium | Row amounts and percentages |

All money roles use monospaced digits. Editing and display use matching weight and
semantic size through the shared UIKit/SwiftUI bridge. Use the role for the amount's
importance, not for the screen it appears on. Fixed 30/36-point money styles and
system headline money are not alternate Plan treatments.

Use native line metrics and default tracking. Do not transplant Argus web line
heights or letter spacing into SwiftUI. Multiline prose and titles wrap. Avoid
fixed-height text containers. Long amounts may shrink within bounded money fields;
other large-text content wraps or scrolls. Keep currency codes visually subordinate
and present exactly once beside an amount where context requires them.

Expandable financial rows are controls, not section headings: use `supporting`
for names, `caption` for counts and `rowAmount` for money/percentages. Keep serif
`section` for real content groups. Equivalent hierarchy uses the same role across
Home, Plan, Chat results and expanded insights.

### Intentional native exceptions

- Home greeting: native title2 semibold system type, not a second expressive hero.
- Navigation bars, Forms, menus and standard native controls retain system semantics.
- Profile identity, avatar initials, icons, voice timers and the Cuadrao wordmark
  have distinct roles. Their existence does not authorize a blanket serif migration.
- Invitation artwork and estimated completion dates are not financial amount roles.
  Keep their approved treatment and ensure artwork does not hide required text.
- Chart ticks may use native caption2. Numeric chart callouts should use a compact
  shared money role when they represent amounts.

Any new exception needs a named purpose and a gallery specimen. Don't override a
shared money role with a local weight, design or hardcoded size.

## 4. Components and selection

Use existing native buttons, sheets, rows and context menus. Preserve approved
icons and icon-only navigation. Major content uses the existing 24-point page
inset, with 8/12/16/24 spacing where appropriate; these are layout conventions,
not a mandate to flatten artwork, chat composition or native Form insets.
Keep touch targets at least 44 points. Show error text alongside semantic color.
The money editor retains its short grouping fade and respects Reduce Motion.
Scroll-edge materials belong behind persistent chrome, never across interactive
content. Surface-specific gestures retain their existing meanings.

### Choices and currency

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

### Selection alignment

`CuadraoChoiceMenu` uses a native Picker with text-only options. The system owns
the checkmark column; never switch a selected row to Label while unselected rows
use Text. Keep captions centered independently of selection indicators. Appearance
checks sit on the preview image; searchable currency checks sit after a Spacer.

## 5. Layout, depth and touch targets

Keep the existing 24-point content inset and the 8/12/16/24 spacing rhythm. Native
Forms keep their own insets. Hierarchy comes from spacing and role, not extra labels
or repeated cards. Financial rows align names left and numeric columns right.

Keep native material behind chrome. Rounded chart surfaces and Plan artwork retain
their approved shapes; use depth for grouping or allocation selection, not to imply
larger financial proportions. Visible icon size and its 44-point hit target differ.
Do not add a pill background merely to enlarge a tap target.

## 6. Surface hierarchy

<a id="locked-plan-hierarchy--october-1-2026"></a>
### Plan

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

The header reads **Lo que viene / What's ahead** with the primary plus beside it.
Remove the old literal Plan heading and its subtitle. Preserve the heading's
preview hold menu and the Para ti / En grupo choice.

### Home welcome and history perspectives

Home uses a compact, static native-system greeting: Hola / Hello plus Profile's
preferred name, or just the greeting if missing. The shared preview profile state
lives in `CuadraoHomeCanvas`; Profile edits and Home read the same value. No date
competes with the greeting. Space switching changes financial scope, not the welcome.
The space creation shortcut uses the shared plain plus. In Household, the existing
avatar stack sits left-aligned between spaces and the amount. It includes the owner
and accepted members only; pending invitations never count as members. Tapping it
opens People. The current preview roster supports the owner and one companion.
The greeting's context menu retains the preview gallery/reset tools.

### Home account and activity shortcuts

Cuentas / Accounts and Movimientos / Activity share the same trailing plain plus.
Home keeps quick creation and row gestures; no accounts-header ellipsis or redundant
configuration cluster. Account rows use the same collection gestures as Plan.
Tapping the Accounts heading opens its management surface, where visible reorder
and archived-account recovery remain discoverable. The entry remains available
when all accounts are archived. Account detail retains visible owner actions;
Home's shortcut does not become the only way to manage a record.

### Home section order and first use

**Ordenar Inicio / Reorder Home** moves whole feed sections through its existing
compact sheet with Cancel, Done and Reset. Greeting, space selector and navigation
stay fixed. Saved section order applies across spaces and survives relaunch. Empty
sections retain their place without adding empty feed content. This is distinct
from the tray-free account and Plan item ordering in section 10.

Personal Home with no accounts offers one add-account action; don't show empty
summary totals or reordering before content exists. Household distinguishes no
household, alone, invitation pending and joined with nothing shared. Inviting or
accepting never silently shares private accounts or creates joint records.

Invitation sharing uses the native share sheet. Creating or copying a link is not
delivery or membership; dismissing the sheet proves neither. Recipient acceptance
and Ahora no / Not now preserve private accounts. Preview acceptance remains local;
production invitation and permission contracts stay in the main roadmap.

### Accounts

Accounts remain in Home's feed, with every non-archived account visible and no
internal list scroller or View all cap. Tap opens the account's balance and activity.
Current shared collection gestures below supersede the original hold-action/reorder
tray experiment. Account detail retains its native back path and visible actions.

Creation requires a type; name and initial balance remain optional. Blank balance
means unknown. Currency belongs at the left of the right-aligned money editor.
Preserve approved vectors, inline validation, whole-unit-first entry and a disabled
save while required input is invalid. Archive preserves history and supports recovery.

The [September 30 Accounts study](../../../docs/specs/cuadrao-accounts-design-lock.md)
is historical provenance, not a second current rulebook. Its earlier ellipsis,
hold-menu and reorder-tray rules are superseded here. Connected reconciliation and
financial contracts retain their own owners.

## 7. Financial charts and storytelling

### Home balance chart

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

<a id="locked-home-and-expanded-insights-direction--october-1-2026"></a>
### Expanded insights

**Quiet Home:** compact welcome, existing space selector, amount, one history line,
and short available-history ranges (for example 1 mes / 1 month). Only offer ranges
supported by the person's recorded history. Keep a subtle, accessible expand icon.
Do not show Evolución / Distribución controls, insight paragraphs or test/sample
copy on Home. Genuine unknown/partial values remain distinguishable from zero;
removing preview disclosures does not authorize invented financial facts.

**Expanded insights:** the native Balance / Actividad choice is right-aligned in
the anchored header, above the compact period/chart controls. Each moving page
starts with a left-aligned period headline above its amount. Week/month show the
first and last calendar dates; year shows the year. Use
`CuadraoTypography.feature` (native title serif) and ink, not the secondary
supporting style. Larger text can wrap without shrinking the title or truncating
choices. Keeping controls anchored lets the period and its evidence move together.
Balance remains recorded net position. Activity uses expenses from the same local
activity owner as the transaction list, filtered by space and currency. Transfers,
income and changing balances do not become spending. Historical fixtures stay in
preview code; connected delivery is still roadmap work.

**Controls:** Semana / Mes / Año and the chart / distribution icons share one compact
row. Adapt to localized labels and larger text, preserving 44-point targets. No
previous/next chevrons or Back to today button in detail. The single period label
above the amount follows the selected range; tick context stays on the axis. Swipe right for older periods, left toward the present;
stop at the oldest available period and today. Real neighboring period pages follow the finger through native paging; do not
use decorative edges with an update-only gesture. VoiceOver custom Previous/Next period actions provide the same navigation.
Long-press inspection must not page; vertical scrolling remains available.

Switching chart/distribution preserves the selected period. For Balance, historical
allocation uses matching recorded account snapshots and identifies their date;
never relabel current assets as a past allocation. Missing observations remain
unknown. The hero remains recorded net balance in both modes. Its current snapshot says
Balance neto · Hoy / Net balance · Today. Label the positive composition separately
as Distribución de activos / Asset allocation, with its own total. Deductions and
net balance remain separate from the positive 100% composition.

**Activity:** vertical bars stack expenses by category. Week uses daily buckets;
month uses calendar-week buckets clipped to the month, labeled with their day
spans; year uses months. Respect the locale calendar when forming week boundaries.
Only recorded dates contribute; future buckets remain unfilled. Colors match category rows, which disclose the same
expense records. The distribution icon shows the selected period's category shares.
`CuadraoExpenseCategoryStyle` owns category colors and vector choices. Reuse
WelcomePalette's Plan accents (pine, clay, sunshine, bloom and overlap); do not
introduce the default neon chart palette. Category icons match Home's 24-point,
1.7-point rounded vector family and 42-point soft tile. Reuse approved Home paths
where their meaning fits; keep new outline vectors in the same asset catalog.
Totals remain actual recorded expenses, never projected spend or savings. Unknown
categories are Otros / Other, never guessed from merchant text.

**Chart storytelling and empty states — founder locked October 1:** expanded
Activity follows chart and takeaway → category breakdown → highlights. Place one
short factual takeaway near the hero amount. Below the categories, show at most
two useful highlights, each with a plain-language explanation, a matching category
icon/color where relevant, and supporting comparison bars or a small trend chart.
Reuse the shared typography, category artwork and palette; no competing icon family.
A highlight opens the supporting records or category detail in the same context.
Show Ver todos / See all only when additional supported highlights exist.

Choose meaningful evidence: a category change, a large transaction explaining a
spike, or a sustained trend with sufficient history. Label both comparison periods
and use a common visual scale. For a running period, compare only the equivalent
elapsed portion of the previous period with adequate recorded coverage; a partial
month must not be compared with an entire completed month. Do not force a trend
from sparse history or color an increase as a moral failure. Balance explanations
must derive from recorded positions/contributors, never infer spending or returns
from balance changes. Home itself keeps its quiet hierarchy.

Empty, first-use, loading and unavailable states follow the shared state rules in
[section 8](#8-empty-loading-and-unavailable-states). Keep historical highlights
labeled with their real window even when the selected month is empty.

Reference basis: the founder-provided Wallet screenshots show highlights below
categories, explanatory comparisons and category icons. The Mobbin search returned
[Wallet period/category breakdown](https://mobbin.com/screens/82a32fee-bf5f-4c39-b4b8-0e002de68d4c)
and [Health explicit no-data states](https://mobbin.com/screens/e60672f4-262f-478f-9326-6a6a2262f43f),
not those exact Wallet highlight screens. This adapts their hierarchy to Cuadrao;
it does not adopt Wallet's typography or duplicate its entire card stack.

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

### Balance change breakdown

The line view answers **Qué cambió / What changed**. Below its chart, show opening
and closing observations with their actual dates, followed by each account's signed
contribution to the change. Use the same scoped currency, debt signs and ownership
share as the hero. Account rows push the existing detail and preserve insights on return.

`CanvasBalanceHistory` owns snapshot matching and contribution arithmetic. One typed
period projection supplies the hero, comparison and breakdown. Row changes must
reconcile to the displayed total change. Never fill a missing opening amount with
zero or call an unexplained balance increase income, earnings or investment return.

A new month keeps the latest known balance and its observation date. A single
observation gives a known amount but no change comparison. If the baseline is inside
the period, name its actual date rather than claiming a full-period comparison.
An empty historical interval may show its last known observation with its date;
never draw a fabricated flat history or use later data. Partial accounts remain explicit.

The stacked view answers **Dónde está / Where it is**: positive assets, individual
accounts and separate deductions. Changing chart mode does not change financial scope.

### History-based insights and interactive periods

Expanded Balance and Activity share native horizontal paging with vertical scroll
inside each page. The period headline, amount and supporting content travel
together; metric and period/chart controls remain anchored. Cancelled drags return
to the same page, completed drags reveal the adjacent period, and range changes
return to the present. Long-hold chart inspection must leave the selected period
unchanged. Home retains its compact inspection behavior.

Activity highlights use completed covered months for 6/12-month averages and a
recent-three versus preceding-nine category comparison. Covered zero months count
in averages. Incomplete months and future pages never leak into these windows.
A sustained category comparison needs activity throughout both windows, not an
isolated large expense. One or two supported highlights sit below categories;
Ver todos / See all opens the full collection grouped into averages and categories.
Each insight opens its supporting monthly records. Current-period comparisons
still use equal elapsed coverage. No history means no invented average or trend.

`CuadraoAllocationBar` owns the dimensional bar for both financial views. Geometry,
selection lift, Reduce Motion fade and proportional widths agree across views;
asset types and expense categories retain their own meaning and shared palette.

## 8. Empty, loading and unavailable states

Use one shared chart-state treatment. Soft static silhouettes fade into the page,
with a restrained Cuadrao ornament using the Plan palette. Decorative shapes have
no axes, values, category encoding, inspection gestures or accessible data points.
They identify the missing content without pretending to be records.

| State | Presentation and behavior |
| --- | --- |
| Covered current month with no expenses | Recorded zero, compact artwork and a localized month-specific line such as Octubre empieza aquí; explain that no expenses are recorded |
| Covered historical period with no expenses | Recorded zero and neutral past-period copy; don't call it a new beginning |
| First use with no history | Welcoming artwork and one working record-entry action |
| Incomplete or unavailable history | Distinguish unknown from zero; omit unsupported comparison claims |
| Real records, even one | Real chart immediately; leave future buckets empty |
| Loading | Same visual footprint with subtle temporary motion; freeze motion for Reduce Motion |

Empty is settled; loading is temporary. Do not shimmer a permanent empty state or
invent waiting in a synchronous preview. The gallery can demonstrate loading; an
actual surface shows it only while a real operation is pending. Historical insights
may remain below a new month's empty state with their actual date window visible.
Keep period navigation available; do not silently switch to the previous month.

References: [Wise empty monthly spending](https://mobbin.com/screens/409c5a70-c57f-4abc-a2e4-f8361af101ba),
[Klarna faded chart forms](https://mobbin.com/screens/1b5919b4-9b02-43db-8e30-540ea5f01fce),
[N26 balance breakdown](https://mobbin.com/screens/3dd2aac4-95c3-4f96-b2ae-bf7455f3400d),
[Copilot account changes](https://mobbin.com/screens/935c477f-d2a5-43b4-b68b-1640269c698e).
These references informed the approved adaptation; they do not define Cuadrao's fonts.

## 9. Money editing

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

## 10. Gestures and continuity

### Collection gestures

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

Native period paging follows the finger and settles or cancels naturally. Chart
inspection is tap or hold, leaving ordinary horizontal paging and vertical scrolling
available. Motion communicates state and continuity. Reduce Motion uses restrained
fades instead of lift or decorative animation. Return preserves selected scope,
period and category. A date boundary never resets financial facts.

## 11. Capture, Chat and Recents

Use these native capture and Recents conventions. The production web behavior
remains in the Argus guide.

- The attachment action is **Escanear** in Spanish and **Scan** in English,
  with a document-scanner symbol. Photos and files remain independent entry points.
- Apple's native document scanner owns capture, page cropping and retakes. Cuadrao
  owns entry, saved drafts and review around that native screen. Delivery and the
  interpretation boundary belong to [roadmap C01](../../../docs/specs/argus-execution-board.md#c01--native-scan-and-receipt-split).
- Recents uses title-first rows, separate Pinned/Recent sections, unread/current
  indicators, and one conversation object shared with Chat and Search. Do not repeat a sample subtitle on every row. Dates derive from the last
  message timestamp, shared with Search; metadata changes do not update recency.
  Render Hoy/Ayer or Today/Yesterday, then a localized short date (including the
  year for older years). Unknown dates remain absent. Preview fixtures have explicit
  sample message dates; these are not backend history.
- Swipe right pins/unpins; swipe left archives or restores. Rows show quiet dates at the trailing edge, with no visible ellipsis.
  Touch-and-hold and VoiceOver actions expose the same contextual commands.
  Pin uses amber, archive uses slate, restore uses Cuadrao green; delete retains
  its destructive red treatment in the menu, not a new swipe action. Mark read/unread comes first, followed by pin, rename, archive and delete.
  Delete requires confirmation and retains recovery in Deleted. Actions on a row
  never also open it. Opening temporary-chat destinations keeps the existing discard
  confirmation. Archiving/deleting the active regular chat opens a fresh chat.

### Receipt capture and review

Capture saves a draft and opens a compact review. **Después / Later** lets the person
leave immediately; leaving never confirms an expense.
Return through the existing Chat or group entry. Do not add a top-level receipt
inbox or automatically reopen review on launch.

Personal Chat, group Chat and Plan open the same receipt identity. Generic files
remain attachments unless the person chooses the receipt journey. Keep merchant,
date, category and total readable before revealing editing controls. Use the shared
money editor and category symbols. A keyboard appears only when editing requires it.

A group receipt inherits the group's fixed currency. Confirm the payer and people,
propose an equal split, and reveal item assignment under **Por consumo / By item**.
Shared items retain one price and several people. Show how many items still need
assignment. Included tax and service appear once; an added tip is separate.
The final review shows each person's share before one explicit confirmation.

Color explains direction. **Te deben / You're owed** uses the positive pine accent;
**Debes / You owe** uses a legible warm clay accent. Settled amounts use a quiet
neutral treatment. Always retain the direction label and symbol. Category colors
continue to describe categories, not debt, and destructive red remains separate.

Location is optional and attached only through an explicit choice. Label a capture
pin as where the receipt was scanned, not as the merchant's address. Denied access
never blocks a draft. A later review must not relabel the phone's current location
as the original capture location.

Prepared examples demonstrate the proposed automatic categorization and review.
An imported image or file must not acquire invented merchant, amount or item data.
Real extraction and connected posting remain roadmap work.

References: [Apple document camera](https://developer.apple.com/documentation/visionkit/vndocumentcameraviewcontroller),
[scan output](https://developer.apple.com/documentation/visionkit/vndocumentcamerascan),
[Apple gestures](https://developer.apple.com/design/human-interface-guidelines/gestures),
[Claude title-first history](https://mobbin.com/screens/9059f305-c9bb-44b9-b0fe-efe19e50a428),
[Messages contextual swipe controls](https://mobbin.com/screens/1ad68688-b638-4f85-b754-7ef96f6d45e5).
The exact gesture mapping above is Cuadrao's adaptation, not a claim that these
reference apps use the same mapping.


October 1 refinement: the founder replaced the visible Recents ellipsis with
last-message dates. Swipe colors adapt [Fiverr's amber star](https://mobbin.com/screens/d6624e4d-927d-46b3-a3f1-d763ef7dd04a)
and [Telegram's gray archive](https://mobbin.com/screens/7b4ae82f-5122-4626-82c9-a6ef11bea8dc).
The row's shared contextual actions are exposed through Apple's
[accessibility actions](https://developer.apple.com/documentation/swiftui/accessible-controls).

### Search and Profile boundaries

Search retains its Accounts, Activity, Plans, Chats, Files and Memory perspectives.
Financial currency filters do not filter nonfinancial content. Household excludes
private chats, source files and memory; a preview filter is not authorization.
The October 2 support-surface assignment reopens Profile polish within the existing
identity and App, Account, Support groups. Settings keep literal native headings.
Avatar themes use the existing palette and icon family. A personal photo uses
Apple's image picker, a circular preview, replacement/removal and the same editor
Save/Cancel boundary. One avatar value owns the active initial, theme or photo;
loading a photo cannot replace a newer choice. The preview retains only a small
re-encoded working source and derived avatar, without source metadata, for the
session. Crop/reposition uses a circular preview with native pan/zoom; an accepted
crop changes only the editor draft until profile Save. Crop Cancel and profile
Cancel retain their separate boundaries. Reopening the crop uses the retained
working source, so repeated edits do not repeatedly crop the thumbnail. Home reads the same
preferred-name value. Appearance retains its existing preference owner. Server
upload and connected account operations remain separate work. The October 2
scope decision keeps QR codes attached to plan invitations. Profile QR, usernames
and public profile discovery are deferred; Profile needs no extra entry point.
Keep the existing avatar family and native identity typography.

A plan code card inherits its plan's artwork or selected cover, name and member
context. The QR sits on an opaque light panel with a clear four-module margin;
art stays outside the code. On-screen and exported cards share one composition.
The native share sheet owns user-directed export. Sample-code wording travels
with preview exports, and scanning must not imply a live invitation until the
invitation contract is connected.

Profile keeps the main navigation on its landing page, with clearance inside the
scrolling content so Sign out stays above it. Pushed Settings pages hide the main
navigation and return through native Back. The navigation path owns this state.

Generic feedback borrows Argus's comment, problem and idea categories. Only a
problem opens the title, reproduction steps and expected/actual outcome fields.
Switching categories preserves each draft; Save draft accepts unfinished text.
Conversation-specific ratings and context consent belong to contextual feedback,
not the Settings entry. Submission and durable intake remain roadmap work.

Search opens account and plan results in its own navigation stack. Chat handoff
has an explicit return to Search and preserves the current query and filters.
An empty perspective describes that content type. A no-match state preserves the
query and offers a clear way to remove it or reset the active filters.

Updates is a quiet inbox with read/unread state, source-linked rows and direct
access to notification preferences. Opening a detail keeps Back anchored to the
inbox. A contextual suggestion is not a new financial event; do not invent an
event date, threshold crossing or milestone from a current value. Ordinary
transactions and chat messages do not each earn an inbox notification. The bell
and list derive unread state from the same visible items. Delivery preferences
control future delivery channels; disabling them does not erase the inbox.
The current preview keeps read state and edited profile fields for the session.
Connected identity and durable inbox state belong to the main roadmap.

Empty inbox and no-match states use small Cuadrao artwork and one useful recovery
action where available. Reserve chart silhouettes for financial chart states.
Do not add permanent loading motion or test disclosures to these screens.

## 12. Localization and accessibility

Support English and Latin American Spanish in every static label, empty state and
action. Use the app locale for date captions; currency precision and formatting come
from `CanvasMoney`. Controls expand for localized text and accessibility sizes rather
than clipping or shrinking labels. Preserve clear VoiceOver labels, selected states,
header traits and gesture alternatives. Known zero and unavailable data remain distinct
in spoken output. Art is decorative unless it conveys information absent from text.

Verify real screens in both appearances and larger text. Component previews alone do
not prove keyboard, navigation, scrolling, focus or gesture continuity.

## 13. Implementation owners

| Shared decision | Single code owner | Usage |
| --- | --- | --- |
| Typography roles | [CuadraoTypography.swift](../../../ios/ArgusFoundation/Cuadrao/CuadraoTypography.swift) | Use named roles for expressive headings and amounts. Native navigation titles, text bodies and system controls retain their semantic text styles. |
| Adaptive palette | [WelcomePalette](../../../ios/ArgusFoundation/Cuadrao/CuadraoCanvas.swift) | Pine, sage, background, surface, ink, borders and positive input text. The historical type name remains; do not create a competing Cuadrao palette. |
| Money parsing and caret behavior | [CanvasDecimalInput.swift](../../../ios/ArgusFoundation/Cuadrao/CanvasDecimalInput.swift) | Accounts and Plan use this same native text editor. |
| Currency precision, formatting and limits | [CanvasMoney.swift](../../../ios/ArgusFoundation/Cuadrao/CanvasMoney.swift) | Derive preview limits and formatting here; currency selection/immutability retains its plan/group owner. |
| Numeric preview bridge | [CanvasMoneyValueInput.swift](../../../ios/ArgusFoundation/Cuadrao/CanvasMoneyValueInput.swift) | Adapts existing numeric preview models to decimal editing text; it is not a new financial store. |
| Plan amount composition | [PlanAmountInput.swift](../../../ios/ArgusFoundation/Cuadrao/Planning/PlanAmountInput.swift) | Currency, rounded amount, focus underline and inline error. Accounts keeps its approved bordered, right-aligned composition around the same editor. |
| Choice labels and add shortcuts | [CuadraoChoiceControls.swift](../../../ios/ArgusFoundation/Cuadrao/CuadraoChoiceControls.swift) | Shared value/caret, native single-selection menu, fixed code and section plus. |
| Balance period and account changes | [CuadraoBalancePeriod.swift](../../../ios/ArgusFoundation/Cuadrao/CuadraoBalancePeriod.swift) | One observed opening/closing pair, signed contributions and matching allocation; reuses `CanvasBalanceHistory`. |
| Empty and loading treatment | [CuadraoChartState.swift](../../../ios/ArgusFoundation/Cuadrao/CuadraoChartState.swift) | Shared decorative forms; `CanvasSpendingStory` classifies financial states. Loading is a gallery specimen until a real operation needs it. |
| Expanded chart controls | [CuadraoChartControls.swift](../../../ios/ArgusFoundation/Cuadrao/CuadraoChartControls.swift) | Icon view choice and localized period choice, including selected accessibility state. |
| Account management | [CuadraoAccountsCollection.swift](../../../ios/ArgusFoundation/Cuadrao/CuadraoAccountsCollection.swift) | Native ordering and archive recovery over the existing shared account model. |
| Reference gallery | [CuadraoDesignGallery.swift](../../../ios/ArgusFoundation/Cuadrao/CuadraoDesignGallery.swift) | Uses real shared components. Access from a hold on Home's greeting → Guía visual / Visual guide, or launch with `--design-gallery`. Preview-only. |

## 14. Reference gallery and evolution

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

The gallery also shows primary/secondary/row money beside the shared editor and the
empty-month, first-use, unavailable and loading treatments. Use it as a living specimen,
not a screenshot-only style sheet. The main roadmap owns implementation status and
unfinished connected work; this guide owns the approved visual and interaction rules.
