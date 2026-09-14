# Menus and settings width contract

Founder-directed 2026-09-14: menus and settings follow the mobile shell's 720px
threshold; 1024px is reserved for the run dossier and its accompanying controls.

## 1. Why

The active grounded-finance roadmap's known gap mixes desktop rails with phone
sheets at 720–1023px. Product truth calls for simple, mobile-friendly chat
continuity. The mobile shell spec already owns the intended behavior.

## 2. Locked decisions

1. Use the existing `useResponsiveLayout` owner, with no new width constants or
   device detection. Below 720px menus, settings, sources and Search row actions
   use their mobile form. At 720px they use their wider form.
2. Preserve the dossier's sheet, activation and pinned conversation action below
   1024px. Its third pane starts at 1024px.
3. Sweep ChatHeaderMenu, GuestSettingsMenu, ProfileMenu, ChatCommandPalette,
   paletteLayout, DiscoverySourcesPanel, AdaptivePanel, SidebarShell,
   NextStepsSection, EmptyChatSurface, ChatMessage, ChatInterface and useMobileShell.
   Record the disposition of each, including unchanged decisions and CSS.
4. Open every reachable menu and settings surface at 390px for guest and
   registered fixtures. Report additional inconsistencies with screenshots.
5. Capture English and Spanish evidence for both identities at 390, 719, 720,
   1023, 1024 and 1280px. Check tablet coarse-pointer access and resizing too.

## 3. Reserved / parked scope

- Model-facing text, interpretation, backend, data contracts and persistence.
- Paid calls, live API turns, live backtests, deployment and merging.
- Additional UI findings beyond width alignment are reported, not silently
  folded into this fix.

## 4. Contract gates

- `web/lib/responsive-layout.ts`: clarify ownership of both thresholds.
- Breakpoint browser specs and affected unit expectations.
- Durable evidence and the component sweep under
  `docs/reports/evidence/menu-settings-width-contract/`.
- API and data models do not change.

## 5. Execution contract

- One worker PR from `codex/private-alpha-next`, targeting the same branch.
- Original fetched integration base: `039189128ea6ffcf59be73f3564fd936f191f662`.
- First commit records this spec; subsequent commits implement and verify it.
- Proof: failing rendered boundary regression before the fix; green focused
  unit, lint and type checks; the hermetic browser matrix; existing affected
  breakpoint baselines at the unchanged 100-pixel tolerance; screenshots read
  visually; clean Codex review and green CI at the PR head.
- Record current integration, semantic overlap, merged-tree modularity budget,
  exact PR head and evidence revalidation in the terminal audit after review.
- Stop at the reviewed PR. The founder merges.

## 6. Stop conditions

- A second Codex finding on the same mechanism: stop and report instead of
  fixing again.
- Required model-facing changes or paid/live calls: stop and report.
- A confirmed blocking requirement exceeds this width lane: report the
  requirement and evidence without expanding the implementation.

## Sources

- `AGENTS.md` and the five canon documents.
- `docs/specs/argus-grounded-finance-roadmap.md`, known gaps.
- `docs/specs/private-alpha-next-decision-memo.md`, chat-first continuity.
- `docs/superpowers/specs/2026-08-06-mobile-pwa-responsive-shell.md`, sections 1–6.
- `web/lib/responsive-layout.ts`.
