# Menus, settings and modal audit

Authority: [BREAKPOINTS.md](../../../BREAKPOINTS.md), built on DESIGN.md section 8.
720px introduces rails; settings remain sheets through Tablet and become anchored
menus at 1024px. The threshold move from `f00be870` was restored in `055643d2`.
The original committed breakpoint baselines are unchanged.

## Confirmed fixes

| Finding | Evidence before | Change and verification |
| --- | --- | --- |
| Auth settings duplicated chat guest settings: a phone popover, unnamed theme controls, and a language dialog that ignored Escape and let Tab reach the login form. | [390px menu](audit/before/guest-en-dark-390-auth-settings-menu.png), [language interaction](audit/before/guest-en-dark-390-auth-language-interaction.json) | `SettingsMenu` now renders the existing `GuestSettingsMenu`. [Phone sheet](audit/guest-en-dark-390-auth-settings-menu-fixed.png), [desktop menu](audit/guest-en-dark-1024-auth-settings-menu-fixed.png). Six-cell tests verify shape, named controls, theme/language changes, Tab containment, Escape, Back and focus return. |
| Account deletion opened behind the parent Data Controls sheet below 1024px while holding keyboard focus. | [720px hidden request](audit/before/registered-en-dark-720-account-delete.png), [control hit-tests](audit/before/registered-en-dark-720-account-delete.json) | ProfileMenu renders one child presentation at a time, using the existing centered dialog. [390px](audit/registered-en-dark-390-account-delete.png), [720px](audit/registered-en-dark-720-account-delete.png), [900px](audit/registered-en-dark-900-account-delete.png). Six-cell regression verifies hit-testing, one modal presentation, Tab, Cancel, Escape and Back without submitting anything. |
| Phone sheet controls did not consistently meet the documented 44px floor: Restore was 36px, rename actions 36px, rename input 42px, and language search input 24px. | [loaded deleted rows](audit/before/registered-en-dark-390-deleted.png), [rename measurements](audit/before/registered-en-dark-390-header-rename.json) | The existing `.argus-sheet` owner applies the floor to buttons and text fields below 720px; Feedback's compact checkbox sits in a clickable 44px label. [Deleted rows](audit/registered-en-dark-390-deleted.png), [rename](audit/registered-en-dark-390-header-rename.png), [language](audit/guest-es-419-light-390-language.png). Measured English-dark/Spanish-light regression checks actual bounds and label interaction. |

No model-facing text, backend, data contract, migration, or environment changes
are part of this PR's diff. The fixes reuse existing owners rather than creating
another threshold, settings menu, or overlay stack.

## Width sweep

| Consumer | Audit disposition |
| --- | --- |
| ChatHeaderMenu, GuestSettingsMenu, ProfileMenu | Keep the existing 1024px sheet/menu switch. ProfileMenu changes only child-dialog presentation ownership. |
| AdaptivePanel | Keep 1024px; its settings consumers inherit that rule. |
| ChatCommandPalette and paletteLayout | Keep 1024px for the dossier/preview container and row-action form. At tablet widths Search remains one list with overlay details. |
| DiscoverySourcesPanel | Keep the existing 1024px sheet/side-panel switch. |
| SidebarShell and useMobileShell | Keep 720px drawer/rail ownership. |
| ChatInterface | Keep 720px rail, drawer, guest-settings placement and keyboard-shortcut availability. |
| EmptyChatSurface | Keep 720px starter scrolling/wrapping and shell density. |
| ChatMessage and NextStepsSection | Keep 720px narrow labels; no interpretation or response-copy changes. |
| SettingsMenu on auth pages | The real peer mismatch: replaced the legacy duplicate with GuestSettingsMenu. |
| responsive-layout.ts | Documentation now points to BREAKPOINTS.md and states both stops accurately. Constants and behavior are unchanged. |

## Capture coverage and limits

Guest and registered fixture identities, English dark at 390, 720, 900, 1024 and
1280 CSS pixels, plus Spanish light at 390px. Height is 900px. The audit opens
reachable settings branches, nested pickers, owner menus, confirmation dialogs,
read-only account/legal routes, guest auth settings and auth screens, guest new
chat, Search/dossier/preview, and Sources. The [screenshot index](index.md) links every raw
capture; adjacent JSON records contain dimensions and control hit-tests.

The fixture asserts the actual document language/theme, waits for populated
async content and visible spinners to disappear, and blocks external browser
requests and API writes. Theme/language selection is local browser state.
Screenshots prove rendered chrome with fixtures, not live account behavior or
model answer quality. No model turn, backtest, account edit, deletion, feedback
submission or sign-out was performed. Rating actions are excluded because their
callback writes feedback immediately; the mock write guard blocked exploratory
attempts before any network submission.

Shared Links and Memory remain gated off; unavailable surfaces are not silently
exposed for the audit. Sidebar preferences and keyboard shortcuts are absent
below 720px by design. Guests retain only their current conversation, so their
current dossier is captured; the additional plain conversation preview uses a
registered fixture. The audit does not simulate an on-screen phone keyboard.

## Intentional forms and remaining observations

Centered Profile and confirmation dialogs are already pinned by the existing
baselines. They were not converted merely to resemble settings sheets. Recents
and assistant action popovers also retain their established forms; the explicit
44px rule in BREAKPOINTS.md applies to phone sheet targets.

The audit records two existing observations outside width/form ownership:
Archived Chats still exposes an English Restore accessible label in Spanish,
while Deleted Items translates it; Feedback's Learn more button has no handler.
See the [Spanish archive record](audit/registered-es-419-light-390-archived.json)
and the Feedback footer captures in the index. These do not justify another
layout implementation.

## Existing baseline drift

After restoring implementation and baselines exactly from integration, the
existing 720px settings suite returned **9 passes and 3 failures**. Reading the
actual images showed existing content changes, not a sheet/menu disagreement:

| Existing baseline | Current integration content | Comparison |
| --- | --- | --- |
| Preferences has three rows | Country and currency is now a fourth row | [Expected](audit/baseline-drift/settings-preferences-720-en-dark-expected.png), [actual](audit/baseline-drift/settings-preferences-720-en-dark-actual.png) |
| Archived rows contain only titles | Rows now have a preview subtitle | [Expected](audit/baseline-drift/settings-archived-720-en-dark-expected.png), [actual](audit/baseline-drift/settings-archived-720-en-dark-actual.png) |
| Usage says Messages | Usage now separates Conversation and Searches with sources | [Expected](audit/baseline-drift/settings-usage-720-en-dark-expected.png), [actual](audit/baseline-drift/settings-usage-720-en-dark-actual.png) |

These baselines were not regenerated. This report does not claim that the whole
legacy screenshot suite is green. The new audit uses raw screenshots rather
than turning every chat frame into a permanent baseline. Existing screenshot
comparison tolerances remain unchanged.

## Verification

- Rendered red/green proof for the three fixes, then 296 audit checks plus 44
  focused browser checks passed. Ten skips document unavailable surfaces.
- Frontend unit suite: 1,978 passed; lint: zero errors, eight existing warnings.
- Production build passed; modularity budget passed on the reconciled tree.
- Final exact-head CI/review and screenshot revalidation are recorded in the PR's
  terminal audit after Codex review returns. No merge or deployment is performed.

Original integration base: `039189128ea6ffcf59be73f3564fd936f191f662`.
The first reconciliation merged `d788449385ec93e92609b4692aa0fe8c1981ab58` as
`b9236fc556650739edc850c08149ca531a11c1dd`. Incoming research-recovery rendering
shared ChatMessage but did not change menu owners; the complete fixture audit
revalidates those rendered paths. The subsequent `8b63b089` board correction
changes documentation only. Final fetched integration and merge SHAs belong to
the terminal PR audit.

```sh
cd web
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3267 bun run test:e2e:menu-settings
bun run test
bun run lint
bun run build
```

Use the pinned Playwright script. The isolated fixture server can instead be
started by the config with `ARGUS_BREAKPOINT_BASELINE_PORT=3267`. Do not use
`--update-snapshots` for this audit.
