# Release Notes Disposition and Public-Beta Re-entry Contract

Status: **CURRENT DISPOSITION DELIVERED** by PR #327, merged into
`codex/private-alpha-next` as `22bec7da`. The row is absent; section 4 remains
the founder-controlled contract for any future public-beta return.

Remove the unavailable Release Notes row from Help & Legal now, while keeping
the conditions for a future public-beta return explicit and founder-controlled.

Founder-locked 2026-08-01 after the delivered keyboard-shortcuts and
quick-jump work documented in
[`2026-07-31-keyboard-shortcuts-overlay.md`](./2026-07-31-keyboard-shortcuts-overlay.md).

## 1. Why

- Disabled destinations make Argus look unfinished and provide no current user
  value. This follows `docs/PRODUCT.md`'s simplicity and low-friction product
  standards and `.agent/designs/argus/DESIGN.md`'s anti-clutter direction.
- Argus already tracks technical release truth through exact candidate SHAs,
  release manifests, canary evidence, and founder-controlled exposure, as
  defined by `docs/PRIVATE_LAUNCH_RUNBOOK.md` and
  `docs/release-manifests/TEMPLATE.md`.
- Deployments, validated checkpoints, and user-facing releases are separate
  events. A merged or validated change is not automatically a public release.

The current private-alpha product has no user need for a Release Notes
destination. The honest surface is therefore the smaller one: Keyboard
shortcuts, Terms of Use, and Privacy Policy remain available, while Release
Notes stays absent until it has real content and a working destination.

## 2. Locked decisions

1. Release Notes is not visible before public beta.
2. Remove the row entirely; do not leave it disabled.
3. Do not add a Release Notes feature flag.
4. Do not build a route, page, content store, CMS, database model, GitHub
   integration, automation, notification badge, or version service now.
5. Exact Git SHA and release manifests remain the authoritative internal
   release record.
6. The feature returns only when a real public-beta note and functioning page
   exist.
7. The first future entry should be **Argus Public Beta**.
8. Do not reconstruct or publish the private-alpha development history.
9. User-facing notes describe deployed and exposed behavior, not merely merged
   code.
10. Internal refactors, infrastructure work, tests, and tiny polish do not
    require public notes.

## 3. Future public-beta direction — intentionally open-ended

The direction below is preserved for a later founder decision. It is not
authorization to implement Release Notes now.

- Store notes as simple, static, localized repository content unless a later
  need justifies something larger.
- Publish notes only after meaningful user-visible changes are deployed,
  verified, and exposed.
- Group small fixes into dated entries.
- Show users dates and plain-language changes; technical version numbers do not
  need to be prominent.
- Internally retain the exact Git SHA plus the release manifest.
- At first public beta, the founder may optionally tag the deployed commit
  `v0.1.0-beta.1`.
- Increment a beta identifier only for meaningful public checkpoints, not every
  deployment.
- A release captain should normally write two to five user-facing bullets per
  meaningful release.
- The exact page design, content format, cadence, tag strategy, ownership
  workflow, unread indicator, and automation remain open for a later founder
  decision.

## 4. Re-entry checklist

Release Notes may return only when every item below is satisfied:

- [ ] Founder approval for public-beta exposure.
- [ ] A verified deployed candidate and completed release manifest.
- [ ] At least one real localized release-note entry.
- [ ] A working accessible page.
- [ ] An active menu link replacing the previously removed row.
- [ ] A decided content owner and update process.

## 5. Reserved / parked scope

These items are explicitly parked because the present user job is only to stop
advertising an unavailable destination:

- Release-note page implementation.
- Version tagging.
- GitHub Releases.
- Automatic changelog generation.
- Database or CMS storage.
- “New” badges and read-state tracking.
- Email or in-app announcements.

## 6. Contract gates

The landing contract is intentionally narrow:

- `docs/superpowers/specs/2026-08-01-release-notes-disposition.md` records the
  founder-approved disposition and public-beta re-entry boundary.
- `docs/superpowers/specs/2026-07-31-keyboard-shortcuts-overlay.md` receives one
  dated historical cross-reference because it describes the previously visible
  disabled row.
- `web/components/sidebar/ProfileMenu.tsx` removes only the unavailable row and
  any icon import made unused by that removal.
- `web/public/locales/en/common.json` and
  `web/public/locales/es-419/common.json` remove only the now-unused Release
  Notes keys.
- Focused frontend tests prove Release Notes is absent while Keyboard shortcuts,
  Terms of Use, Privacy Policy, quick-jump behavior, localization, and
  accessibility remain intact.
- `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`, OpenAPI, backend code, database
  schema, migrations, release manifests, and hosted configuration do not
  change.

## 7. Execution contract

- **PR shape:** one normal feature-branch PR targeting
  `codex/private-alpha-next`, with two atomic commits in order:
  `docs(release): record release notes disposition`, then
  `fix(settings): hide unavailable release notes`.
- **Proof required before the PR counts as ready:** the focused Alpha frontend
  test, quick-jump and keyboard-shortcuts tests, frontend lint, frontend
  production build, and browser QA in English and Spanish. Browser QA should
  cover light and dark appearance where practical and verify submenu layout,
  focus, numbering, and console health in addition to the three retained
  destinations.
- **Where it stops:** push the feature branch and open a Draft PR. The founder
  retains merge, tagging, deployment, hosted configuration, and user-exposure
  authority.

## 8. Stop conditions

Stop and report if this narrow disposition requires:

- API, schema, migration, Supabase, authentication, or deployment changes.
- Changes to Omnisearch or shortcut behavior.
- Broader `ProfileMenu` or settings architecture refactoring.
- Creating a public page, version tag, release, or deployment.
- Resolving an active conflicting owner on the same Help & Legal menu surface.

## Sources

### Argus authority

- `AGENTS.md`
- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `.agent/designs/argus/DESIGN.md`
- `docs/specs/private-alpha-next-roadmap.md`
- `docs/specs/private-alpha-next-decision-memo.md`
- `docs/PRIVATE_LAUNCH_RUNBOOK.md`
- `docs/release-manifests/TEMPLATE.md`
- `docs/superpowers/specs/2026-07-31-keyboard-shortcuts-overlay.md`

### External inspiration

None. This is an Argus product-truth and release-discipline decision.

### Inference

Removing a nonfunctional destination reduces visible product debt without
changing any supported workflow. Its future return needs a separate founder
decision because page design, content ownership, cadence, and release tagging
are deliberately unresolved.
