# Native Accounts design review

September 30, 2026. [Approved decisions](../../../../specs/cuadrao-accounts-design-lock.md).
Run the existing Cuadrao design app on simulator
`8AFB6084-8918-416E-9164-E21061306BEC` with
`--cuadrao-design --cuadrao-home --home-populated`.
Add `--design-english` for English. Mirror: http://localhost:3200/.
Reuse `/private/tmp/cuadrao-native-design-build`; no new simulator or build cache.

## Observed checks

- Build/install/launch passed with no reported compiler warnings/errors. Final
  build log: `build_run_sim_2026-09-30T22-38-49-716Z_pid12375_fe864a4d.log`.
- Spanish and English account forms render the nine original SVG account types;
  the six common types appear first, assets are disclosed below.
- Selecting Savings/Loan collapses the type grid and enables Add without a name
  or balance. Blank balance saved as unknown (dash), not zero.
- Native input rendered `12345.67` as `12,345.67`. It accepted `9,999,999.99`.
  Entering `10000000` stopped at the last valid value with a maximum explanation
  and disabled Add. Backspace through grouping cleared the field and error.
  Attempted letters did not enter the decimal field.
- Long press on Mi tranquilidad opened the leading-icon actions without opening
  detail after fixing competing tap/hold gestures. Account-detail (…) uses the
  same actions. Rename form opens with the existing name; name autocorrection
  is disabled after observing the system alter Viaje to Blake.
- Archive hid the account, preserved its amount in Archived accounts, and Restore
  returned it. Undo independently restored an archived account.
- Native reorder handle moved Mi tranquilidad from third to first. Done retained
  that order. Final small layout correction adds space before the drag handle.
- Tap opened the selected account; the primary action opened entry. Entered
  125.50, reviewed it, and saved a preview row in that account's activity.
- Home activity derives from the same preview rows and account names.

## Evidence

- [Final Home](home-final.jpg)
- [Final account detail](detail-final.jpg)

- [Add account · Spanish](add-account-es.jpg)
- [Add account · English](add-account-en.jpg)
- [Hold actions](account-actions.jpg)
- [Archived accounts](archived-accounts.jpg)
- [Reordering](reordered-accounts.jpg)
- [Amount limit](amount-limit.jpg)
- [Entry review](entry-review.jpg)

The English form and limit were captured after the final build. Earlier Spanish
captures retain applicable form/management evidence: later edits changed name
autocorrection, asset custom-share input, reorder trailing spacing, and account
header overflow background. They do not establish untouched final pixels for
those specific edits. Final detail and home captures are saved separately.

## Boundaries and remaining polish

This is a reusable native UI canvas with in-memory fictional data. Relaunch
resets it. Entry Save stages a row only; it does not change recorded balance or
implement ledger logic. The balance-check button explains the connected-app
boundary. Rich transaction types, corrections, reconciliation, institution/date
editing metadata and advanced asset fields remain owned by their existing
contracts and are not claimed complete in this canvas.

Full Dynamic Type/VoiceOver, every currency/paste/caret combination, zero-versus-
blank, custom ownership and every English management interaction have not all
been exhaustively exercised. Input uses Dominican/US separators in these two
review languages. Motion is native and reduced-motion aware, but timing remains
open to founder review. Home composition and bar motion remain unfinished.

The supplied Mobbin captures informed hierarchy/edit mode, not current-version
or animation claims. See the design lock for source URLs and Apple references.
Nothing is pushed, merged, deployed, or connected to real financial services.
