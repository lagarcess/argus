# Mobile PWA Responsive Shell

Founder-locked 2026-08-06. Spec only, no implementation authorized yet.

Board item 3 on [`argus-active-roadmap.md`](../../specs/argus-active-roadmap.md).
This is the public-exposure gate: Argus is not shared publicly while phones are
broken.

**Scope:** browser on mobile, responsive by screen width. Guest and signed-in
alike. Not a native app; there is no native shell in this lane.

**Delivery decision (locked):** responsive PWA polish, the fastest and cheapest
unlock. The native-shell and full-native options recorded on the earlier product
board are closed, not deferred.

## 1. Breakpoints

Custom breakpoints matching `.agent/designs/argus/DESIGN.md` section 8, not
Tailwind defaults. Section 8 explicitly defers this choice to component specs;
this spec closes it. Configure Tailwind to the DESIGN.md ranges rather than
mapping around them.

Two thresholds, because the sidebar and the dossier fail at different widths.

| Threshold | What changes |
| --- | --- |
| **below 1024px** | The run dossier stops being a third pane and becomes an overlay sheet. Three panes need roughly 1250px. Tablets get this. |
| **below 720px** | Full mobile treatment, everything in sections 2 through 8. This is DESIGN.md's own Mobile/Tablet line. |

"Below threshold" in this document means below 720px unless stated otherwise.

## 2. Application shell

The sidebar becomes an off-canvas drawer.

- No sidebar rail is visible. The top bar carries a `=` menu trigger at the top
  left.
- Use `=`, not the Argus mark. A brand mark that is also a control is
  ambiguous. The `A` appears as a static logo in the drawer header, which
  preserves the reveal moment without overloading the logo.
- When the drawer is open the trigger becomes an `X` at the top right inside the
  panel. A control should describe its action, not turn into branding.
- **Web is unchanged.** The existing square-drawer icon stays. Different
  constraints earn different affordances; forcing consistency here costs desktop
  clarity for nothing.
- Drawer width is 80 to 85 percent with a dimmed scrim. Not half: at 390px a
  half-width panel cannot render a conversation title legibly. The remaining
  strip of chat stays visible and tappable.
- Dismiss by `X`, by tapping the scrim, or by swiping.
- Conversation activity indicators aggregate onto the `=` trigger while closed,
  then propagate to their individual rows once the drawer is open.
- Sidebar settings entries are disabled **and invisible**, not greyed out.

### Top bar composition

| Account | Left | Center | Right |
| --- | --- | --- | --- |
| Guest | `=` | chat title | Sign up |
| Registered | `=` | chat title | three-dot menu |

Sign up is pinned top right for guests and does not move. The chat title becomes
the screen heading and needs a shorter generated character limit below
threshold; apply it as a generation rule, not by clipping.

Preserve the existing blur-behind-scroll treatment on the top bar.

### Three-dot menu

Registered only. Its actions are rename, mark read and unread, pin, and delete;
pin and read-state are meaningless for a guest's single conversation.

**Accepted tradeoff:** guests lose rename, because click-to-rename was deferred
in the chat-header-title lane and rename exists only inside this menu. This is a
knowing choice, not an oversight.

Extend the account-kind menu gating already built in PR #274 rather than adding
a second gating mechanism.

## 3. The sheet primitive

One component, three heights. Build it once.

| Surface | Height |
| --- | --- |
| Run dossier | full |
| Discovery sources | about 70 percent |
| Confirmation card capital and dates editor | about 40 percent |

Bottom sheets, not centered modals: centered modals are a desktop pattern, while
sheets are thumb-reachable and swipe-dismissible on both platforms.

The capital and dates editor is board item 2's work and is listed here only so
that lane reuses this primitive instead of inventing a second one.

## 4. Omnisearch and the dossier

Below threshold Omnisearch is collapsed-only. There is no expanded mode.

- Tapping a conversation row opens the dossier as a full-height sheet, focused
  on that conversation, with its full capabilities intact.
- **`Open conversation` is pinned as a sticky primary action** inside the sheet,
  always visible without scrolling. It uses the same pill treatment as Retest.
  Without this, reaching a buried conversation costs a search, a tap, and a
  scroll hunt.
- Row hover actions become a trailing vertical three-dot on each row, matching
  the pattern already used elsewhere. **Not long-press.** Long-press has no
  visual affordance and is undiscoverable; both mobile platforms moved to
  explicit controls for this reason.

## 5. Composer and starter prompts

- Starter prompt pills move above the composer, where they are thumb-reachable.
- They become small pills in a horizontal scroll with a deliberate peek, a
  partially visible next pill, which is what signals that more exist.
- They auto-dismiss once the user sends their first turn.
- No manual dismiss control. An `x` is clutter on something that dismisses
  itself.

## 6. Result and suggestion content

- Suggestion row text must fit without looking clipped. **The backend supplies a
  short form for narrow screens**; the frontend applies a two-line clamp only as
  a safety net. Never single-line ellipsis, which reads as broken. This follows
  the standing rule that the backend owns user-facing copy.
- The conversation activity mini-map rail is **removed below 720px**. Hover does
  not exist on touch, and a hold-plus-wheel gesture would fight vertical
  scrolling, the one gesture that cannot be compromised. `ConversationActivityJumpButton`
  already exists and does the actual job; keep it.
- The rail remains at tablet width and above.

## 7. Confirmation card

Below threshold the action buttons take the same sleek treatment as other
surfaces, sized and wrapped for narrow screens.

**All five actions remain in this lane.** The consolidation to three is board
item 2's work and is explicitly deferred; see the roadmap line item. Removing
the deterministic entry points before multi-edit is reliable would funnel every
edit into the path that currently drops compound edits.

## 8. PWA install

`web/app/layout.tsx` references `/manifest.json` and **no manifest exists**.
There is no apple-touch-icon and no theme-color. Home-screen install does not
look app-like today. This is a prerequisite, not polish.

Required:

- `name`, and `short_name` at 12 characters or fewer, which is what fits under a
  home-screen icon.
- `display: "standalone"` with `display_override: ["standalone", "minimal-ui"]`.
- `theme_color` matching Argus dark `#191c1f`, plus `background_color` for the
  splash.
- Icons at 192 and 512, **plus a separate `maskable` 512**. Without the maskable
  variant Android renders the icon inside a white box, the most common PWA
  polish failure.
- `<link rel="apple-touch-icon">` at 180x180 in the document head, because
  **iOS ignores manifest icons entirely**.
- A `theme-color` meta tag with light and dark media queries.
- `screenshots`, which Chrome uses for a richer install prompt.

**`display: standalone` removes the browser back button.** Once installed there
is no system back on iOS. Every sheet, the drawer, and any flow that relies on
browser back needs an in-app back affordance. This breaks only for installed
users, which makes it the hardest class of bug to notice, so it must be designed
in rather than discovered.

## 9. Defaults

- Theme follows the system setting.
- Language comes from `navigator.language`, not geography. It reflects what the
  user actually set, it is correct for a Spanish speaker anywhere, and it needs
  no IP lookup. A value beginning with `es` selects `es-419`.

## 10. Guest specifics

Everything above applies to guest and signed-in alike. Guest-only points:

- The gear icon moves to the bottom of the drawer. The top bar already carries
  the menu trigger, title, and Sign up; a fourth element breaks it. This also
  matches where signed-in settings live.
- Sign up stays pinned top right and does not move.

## 11. Standing constraints

- Touch targets meet the 44px minimum, and input fields keep a 16px minimum font
  size to prevent iOS auto-zoom, per DESIGN.md section 17.
- Desktop and laptop behavior must not regress. It is already strong.
- No em dashes in user-facing copy in any language. English and es-419 stay
  equivalent.
- Accessibility baseline per DESIGN.md section 19, including visible focus
  states and accessible names for icon-only controls.

## 12. Sources

- `.agent/designs/argus/DESIGN.md` sections 8, 17, 19, 21.
- `docs/specs/argus-active-roadmap.md` board item 3.
- `docs/specs/private-alpha-next-decision-memo.md` section 21 decision filter,
  and section 18 on why mobile became the exposure gate.
- Existing implementation: `web/components/chat/ChatInterface.tsx`,
  `web/components/sidebar/ChatSidebar.tsx`,
  `web/components/chat/DiscoverySourcesPanel.tsx`,
  `web/components/chat/ConversationActivityRail.tsx`,
  `web/components/chat/ConversationActivityJumpButton.tsx`,
  `web/components/sidebar/command-palette/RunDossierView.tsx`, and the
  account-kind menu gating from PR #274.
