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

## Review and evolution

The gallery offers Spanish/English, light/dark and large-text controls. It contains
headings, amounts, a row, a disabled action and working Account/Plan input fields.
Use it to compare states, then verify the actual surfaces: isolated components do
not prove keyboard, scroll or navigation behavior. The gallery does not post data.

For a new feature, reuse the shared roles/components first. When a new pattern is
necessary, mark it experimental in its assigned work; promote it here after review
and migrate equivalent usages together. Update the component owner rather than
copying a style or parser. Preserve each surface's useful personality. Tests should
exercise meaningful behavior and navigation, not freeze every styling literal.
Future chart, receipt, provider and connected-delivery work stays in the roadmap.

## Home balance chart

Home keeps a compact recorded-position chart, with the same debt signs and asset
ownership shares as its amount. `CanvasBalanceHistory` owns that projection;
`CuadraoHomeOverview` owns presentation. Select currencies separately, never add
or convert them. Personal/Hogar retain the existing account-scope owner.

Tap to retain one observed date/value, hold and drag to inspect, and use Hoy/Today
to return to the current balance. The native chart leaves regular vertical
scrolling available. Keep the pine line, subtle fill, readable range labels and
sample-history label in the preview. Missing history gets an empty state; no flat
line, inferred pre-account balances or forecast is invented. A new account or
currency/kind/share change cannot silently borrow old example observations.

The Home link opens Plan as a separate surface; it does not imply its sample
forecast is computed from Home's accounts. Connected history/forecast ownership
and scope-preserving navigation remain in the main roadmap.

### Home welcome and history perspectives

Home uses a compact, static native-system greeting: Hola / Hello plus Profile's
preferred name, or just the greeting if missing. The shared preview profile state
lives in `CuadraoHomeCanvas`; Profile edits and Home read the same value. A localized
date sits above it. Space switching changes the financial scope, not the welcome.
The greeting's context menu retains the preview gallery/reset tools.

Evolución / Distribución (History / Breakdown) replace each other in one overview.
History offers 1 month, 3 months, year to date and all available observations, with
an expanded history sheet for selecting a calendar month. These filters never
invent boundary balances. A past month shows only its recorded dates, not today's
balance. Preview observations span multiple months and stay explicitly illustrative.
Distribution uses a flat positive-assets bar with category disclosure rows; debts
and other negative contributions appear separately. All values derive from the
same signed contribution function, with asset shares and currency separation.

References: [Wealthsimple history](https://mobbin.com/screens/667bf371-6e73-42f5-b179-574e62d9b64b),
[Public allocation](https://mobbin.com/screens/07c1ff8c-f0da-4bf0-919a-d21b2ac5ff43),
and [Origin disclosure](https://mobbin.com/screens/7edb40e1-bbbe-4c1a-9916-f10f943d7685).
This is a founder-reviewable UI iteration; connected history remains in the roadmap.
