# Responsive portability correction

At head `300c49223fdb2c3a3d62c2d55c2ed9f0a228e721`, both Linux CI runs
([push](https://github.com/lagarcess/argus/actions/runs/35824130145),
[pull request](https://github.com/lagarcess/argus/actions/runs/35824152163))
passed 58 browser cases and failed two Spanish 320px overflow checks.
Both saw the same transaction header, one underneath the import dialog.
The retained Linux screenshots show the action row exceeding the viewport.

`PageHeader` already owns the action row, but TransactionsPage nested another
row inside it. The shared descendant rule disabled shrink on both rows. Linux
font metrics made their combined intrinsic width overflow by four pixels.
Remove the redundant row and let the canonical header row shrink. Existing
wrapping then keeps the actions inside the viewport without hiding content or
weakening the one-pixel overflow assertion.

A regression applies increased letter and word spacing to the header actions.
It reproduced 55 pixels of overflow before the fix and passed afterward.
The affected EN/ES 320px experience journeys, all 13 Spanish mobile routes and
the text-spacing regression then passed, four cases in 20.4 seconds. The build
also passed. Local screenshots were recaptured; the import dialog was visually
inspected. The final Linux full-suite rerun is recorded in the PR terminal audit.

`source.json` fingerprints the corrected source/test tree. Against
`../final/source-followup.json`, only TransactionsPage.tsx, platform/shell.css
and e2e/platform.spec.ts changed. Backend, core, composer, currency and import
parser evidence remains valid. Earlier header screenshots describe the prior
layout; this directory and the final CI artifact supersede affected frames.
