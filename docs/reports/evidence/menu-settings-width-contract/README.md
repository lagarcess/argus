# Menus and settings follow the width contract

The menus, settings panels, source panel and Search row actions now switch at
720px. Search's dossier container and its activation/pinned action keep 1024px.
This closes the active roadmap's width mismatch; it does not claim all phone
settings issues are fixed.

## Scope and reproduction

Original fetched integration base: `039189128ea6ffcf59be73f3564fd936f191f662`.
Worker: `codex/menu-settings-width-contract`, PR target `codex/private-alpha-next`.

Before the fix, the rendered registered Settings test at 720px expected zero
`.argus-sheet` elements and received one. The captured failure is
[registered Settings at 720px](before/registered-settings-720.png). After the
change the same assertion passed. No model-facing text or backend code changed.

The full app runs locally with mock authentication and intercepted API reads.
The identities, stored messages and dossiers are fixtures, not live accounts or
live result-quality evidence. All external browser requests are blocked; API
writes are rejected except the intercepted read-boundary acknowledgement. No
model turns, simulations, feedback submissions, account edits or sign-outs run.
The persisted run fixture exercises the dossier container; the menu change is
strategy-agnostic. A plain conversation preview also exercises that container.

## Width sweep

| Component | Disposition |
| --- | --- |
| ChatHeaderMenu | Menu and dismissal ownership use 720px; existing `tablet:` row styling already agrees. |
| GuestSettingsMenu | Sheet below 720px, anchored settings menu from 720px; drawer/header placement still comes from ChatInterface. |
| ProfileMenu | Sheet below 720px, popover from 720px. Existing click handling opens submenus on touch; hover only accelerates it. |
| AdaptivePanel | Shared owner now switches at 720px. Appearance, Language, Country, Sidebar, Usage, Archived/Deleted, Memory, Shared receipts, Feedback and receipt-sharing panels inherit it. Gated panels were inspected statically, not exposed by the test. |
| DiscoverySourcesPanel | Sheet below 720px, right side panel from 720px. Removed redundant `sm:` styles from the wider-only branch. |
| ChatCommandPalette / paletteLayout | Collapsed-only Search and explicit row menu below 720px. Wider row/date spacing follows the same boundary; pointer CSS retains a 44px explicit menu for coarse/hybrid pointers. |
| Search dossier | The shared run/answer/conversation-preview container, row activation, third pane and pinned Open conversation action retain 1024px. Container/divider/preview CSS now names `desktop:` rather than an independent 768px form. Outer Search padding uses `tablet:`. |
| SidebarShell | Already uses 720px for drawer/rail. No change. |
| useMobileShell | Already closes the drawer when entering tablet width. Rail/drawer remount closes the menu; it reopens in the current form. No change. |
| ChatInterface | Already uses 720px for drawer, guest settings placement, shortcuts and activity rail. No change. |
| EmptyChatSurface | Already uses 720px for starter scrolling/wrapping and layout. No change. |
| ChatMessage / NextStepsSection | Already pass/use the 720px narrow-label decision. No model-facing or user-copy change. |

The shared threshold owner remains `web/lib/responsive-layout.ts` and
`useResponsiveLayout`; no new thresholds or device sniffing were added. Panel
size tokens `sm`, `md`, `lg` are maximum-width names, not media queries.

## Browser coverage

[The lane spec](../../../superpowers/specs/2026-09-14-menu-settings-width-contract.md)
owns the acceptance contract. The screenshot grid covers every combination of:

- 390, 719, 720, 1023, 1024 and 1280 CSS pixels, at 900px height.
- English and Latin American Spanish.
- Guest and registered fixture identities, dark theme.
- Header owner menu (registered) or guest shell, Settings, Language, Search,
  dossier and Sources. Guests correctly have no header owner menu.

Additional captures cover registered Search row menus below 720px; touch
Preferences/Search row menus at 720 and 1023px; plain conversation previews at
720, 1023 and 1024px; and the complete reachable phone settings walk. Existing
720px settings baselines were updated separately, including Sidebar preferences.

Representative boundaries:

| Surface | 719px | 720px | 1023px | 1024px |
| --- | --- | --- | --- | --- |
| Registered Settings | [sheet](darwin/settings-registered-en-719.png) | [popover](darwin/settings-registered-en-720.png) | [popover](darwin/settings-registered-en-1023.png) | [popover](darwin/settings-registered-en-1024.png) |
| Guest Language | [sheet](darwin/language-guest-es-419-719.png) | [dialog](darwin/language-guest-es-419-720.png) | [dialog](darwin/language-guest-es-419-1023.png) | [dialog](darwin/language-guest-es-419-1024.png) |
| Sources | [sheet](darwin/sources-registered-en-719.png) | [side panel](darwin/sources-registered-en-720.png) | [side panel](darwin/sources-registered-en-1023.png) | [side panel](darwin/sources-registered-en-1024.png) |
| Dossier | [sheet](darwin/dossier-registered-en-719.png) | [sheet](darwin/dossier-registered-en-720.png) | [sheet](darwin/dossier-registered-en-1023.png) | [pane](darwin/dossier-registered-en-1024.png) |

The [390px findings](phone-findings.md) include screenshots and measured control
geometry. These are recorded pre-existing inconsistencies, not fixes in this PR.

## Reproduction commands

Use the pinned Playwright 1.59.1 scripts, not a freshly resolved `bunx` package.
The config starts a mock-only local server; use an unused port in shared worktrees.

```sh
cd web
ARGUS_BREAKPOINT_BASELINE_PORT=3267 bun run test:e2e:menu-settings
ARGUS_BREAKPOINT_BASELINE_PORT=3267 bun run test:e2e:breakpoints --grep 'settings 720'
bun run test
bun run lint
bun run build
```

For an already running dedicated fixture server, set
`PLAYWRIGHT_BASE_URL=http://127.0.0.1:3267`. New evidence generation uses
`--update-snapshots`; acceptance reruns do not. Both screenshot configs retain
`maxDiffPixels: 100`, `threshold: 0.2`, CSS pixel scale, frozen animations,
UTC timezone, and platform-separated baselines. Phone screenshots show a
Chromium viewport; they do not simulate an iOS keyboard.

The terminal PR audit is posted after final Codex review and records the exact
head, current integration, overlap disposition, CI, and screenshot revalidation.
No merge or deployment is performed by this lane.
