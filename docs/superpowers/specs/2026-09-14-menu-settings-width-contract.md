# Menus, settings and modals: breakpoint audit

The authority is [docs/BREAKPOINTS.md](../../BREAKPOINTS.md), built on
[DESIGN.md section 8](../../../.agent/designs/argus/DESIGN.md#8-responsive-behavior).
Its existing visual baselines own rendered truth. This spec does not define a
second width contract.

## Corrected scope

Founder correction, 2026-09-14: restore the threshold move from `f00be870` and
its changed committed baselines. Settings stay sheets in Mobile and Tablet;
720px introduces rails, and 1024px introduces anchored settings menus and dossier
panes. Keep the worker branch `codex/menu-settings-width-contract`.

Audit every reachable guest and registered menu, settings surface and modal in
English dark at 390, 720, 900, 1024 and 1280px, plus Spanish light at 390px.
Record screenshots and actual contract or same-band peer inconsistencies. Fix
only confirmed violations; keep intentional baseline-pinned forms. Do not
regenerate committed baselines for the discarded threshold move.

## Boundaries and evidence

- No model-facing text, paid calls, real turns, simulations or account writes.
- Use isolated fixture browser traffic, real rendered UI and control hit-tests.
- Keep raw audit captures separate from the existing screenshot baselines.
- The shared responsive-layout docstring may point at the authoritative docs.
- Preserve original integration base `039189128ea6ffcf59be73f3564fd936f191f662`;
  reconcile by normal merge, report semantic overlap and verify the merged tree.
- Final delivery: PR targeting `codex/private-alpha-next`, green CI and clean
  Codex review at the exact head. Write the terminal audit after review returns.
- A second Codex finding on the same mechanism stops further fixes: report it.
- Do not merge or deploy.
