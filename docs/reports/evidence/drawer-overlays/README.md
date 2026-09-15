# Drawer overlay viewport repair

## Reproduction and evidence

Integration base: `350e3dca8f573f5dfd61f1f753d8ed16a2724c9e`.
Before capture commit: `8817b41b` (production code unchanged from the base).

All captures use Chromium, a 900px viewport height, device scale 1, fixture API
reads, and `reducedMotion: no-preference`. Screenshots allow animations and are
captured after finite animations finish. No provider calls or product writes.
The JSON beside each PNG records measured geometry and motion preference.

The 25 cells cover all seven requested surfaces at 375 and 390 in English dark,
all seven at 390 in Spanish light, and Usage/Profile at 720 and 1024. Before the
fix, the four phone sheets measured 82% of the viewport: 307.5px at 375 and
319.796875px at 390. Profile and Delete all were centered in that strip. Delete
account was already centered correctly. The 720 and 1024 cells were correct.
The additional assertion that the finished drawer has `transform: none` failed
for Delete account too; its dialog geometry itself passed.

`before/` and `after/` contain matched full-viewport screenshots, not crops that
could conceal a misplaced panel. Dev-only badges remain visible in both sets.

## One placement owner

`withViewportPortal` mounts full-screen overlays directly under `document.body`.
It gates the entire surface until client mount so focus/history hooks register
only after the portal exists, with an empty server and hydration render. Shared
BottomSheet, AdaptivePanel's desktop dialog, and ConfirmDialog use it, together
with the custom full-screen surfaces found in the sweep. ProfileMenu no longer
owns special portals for its sheet or account-deletion dialog. Its desktop
anchored menu keeps its existing anchor-based portal. GuestSettingsMenu now
leaves sheet dismissal to AdaptivePanel: its desktop outside-click listener
otherwise mistakes a portaled theme button for a click outside the menu.

The drawer and sheet entrance animations use `backwards` fill. Their transforms
apply during entrance and disappear after completion; drag transforms still
work while the gesture is active. Portal isolation also protects overlays during
those animations and gestures.

Static markup tests render the inner surface to retain their content assertions.
The browser matrix exercises the public portaled exports, viewport placement,
44px phone sheet controls, Tab containment, and Escape. It also applies each of
`transform`, `filter`, `will-change: transform`, and `contain: paint` to the drawer
and asserts that the opened overlay's rectangle does not move.

## Containing-block sweep

Scope: `web/app/globals.css` and every file under `web/components`. Searched CSS
properties, inline styles, Tailwind transform/translate/scale/rotate/blur and
containment utilities, animation classes, and every `fixed inset-0` owner.

| Owner or treatment | Disposition |
| --- | --- |
| `.argus-drawer-enter`, `.argus-sheet-enter` | Fixed: release the finished transform. Descendant overlays escape through the shared portal, including during drag. |
| BottomSheet, AdaptivePanel desktop dialog, ConfirmDialog | Fixed at their public exports with the shared portal owner. |
| SidebarDrawer, ProfileDetailsDialog, ProfileDeleteRequestDialog, KeyboardShortcutsOverlay, RecentsQuickPeek, ChatCommandPalette | Fixed at the overlay export. All full-screen sidebar overlays are body siblings. |
| GuestConversionModal, GuestNewConversationDialog, DiscoverySourcesPanel | Fixed at the overlay export. Mobile sources still use BottomSheet; desktop sources retain the side-panel shape. |
| `.argus-card-reveal`, confirmation/result entrance animations | Retained. They deliberately transform cards and set `will-change: transform`; their menus, editors and sources now derive viewport placement from portaled primitives. The cards retain their visual animation. |
| `.argus-chip-appear` on StrategyConfirmationCard symbol spans | Retained: transforms a leaf symbol, with no full-screen descendant. |
| `argus_infinity_pulse` keyframes | Retained: no component usage found; no reachable overlay host. |
| `animate-in` on ChatMessage, ChatHeaderMenu, ChatHeaderTitle, sidebar title text, ChatToast, DevModeBadge | Retained. Message/header child overlays use the portaled primitives; title, toast and badge animation nodes have no full-screen descendants. |
| ChatSidebar `will-change-[width]` and `overflow-hidden` | Retained. Width does not establish a fixed containing block; full-screen children now portal outside clipping too. |
| GuestSettingsMenu translated anchored menu | Retained: intentional desktop positioning; its language/feedback panels use AdaptivePanel. |
| ChatSidebar trailing actions, CommandPaletteRowActions and RecentsQuickPeek translated row decorations | Retained: local positioning; action dialogs use ConfirmDialog/AdaptivePanel. |
| Tooltip and RecentChatActions fixed popovers | Already portal directly to body; anchor-derived position retained. Tooltip's translations apply to itself. |
| Dialog wrapper `backdrop-blur` and sheet/drawer/Omnisearch/guest scrims | Retained for visual treatment. Scrims have no child overlay; nested full-screen dialogs now portal independently of their parent wrapper. |
| ConversationActivityRail preview, ChatInterface fades, Tooltip/DevModeBadge/ReceiptActionBar backdrop blur | Retained. Decorative/leaf content, with no full-screen descendant. ReceiptActionBar is page chrome, not a full-screen overlay. |
| Icon/control hover, active scale, rotation and translation utilities | Retained in AlphaLegalPage, AuthForm, SidebarHeader/NavButton, ProfileDetailsDialog, ChatShellMenuTrigger, DecisionAffordance, ConfirmationDirectEdit, DecisionEditor, ChatCommandPalette, FeedbackDialog, UsageModal, ExecutionDetails, ResultChartExploration, MemoryRecallNote, NextMoveRow, EmptyChatGreeting, ConversationActivityRail and ChatMessage. These are local controls or leaf decorations; full-screen children use the shared primitives. |
| Other filter, CSS contain or `will-change` hosts | No additional declarations found. Array `.filter()` and `text-transform` are unrelated. |

A structural ownership test rejects a new `fixed inset-0` component without
`withViewportPortal`. There are no breakpoint or user-facing copy changes.

## Verification command

From `web/`:

```sh
ARGUS_OVERLAY_EVIDENCE_DIR=../docs/reports/evidence/drawer-overlays/after \
  bun run test:e2e:menu-settings drawer-overlay-motion
```

The fixture's motion-on option bypasses both reduced motion and `FREEZE_CSS`.
Existing frozen screenshot baselines retain their settings and pixel budget.
