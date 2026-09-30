# Cuadrao Home spaces preview

September 30, 2026. Native SwiftUI design canvas, sample data only.

## Decision and references

The founder explicitly selected the original horizontal space selector on Home:
Personal, Household, and Add; not stacked groups. The selected space uses dark
semibold text, other spaces muted text. No pill, underline, currency chip or
additional navigation-bar destination. Add remains a 44-point target while long
space lists scroll horizontally. All active accounts remain visible within Home.

Sources inspected:
- Existing MVEE Financial spaces and Managing private spaces sections, and DESIGN.md's September 28 context refinement.
- [Notion workspace flow on Mobbin](https://mobbin.com/flows/4dc02d6b-4c78-4bf4-b168-92b1fa43b10e): switching context separately from content; management in a sheet. We do not copy its account switcher or navigation pills.
- [Things grouping on Mobbin](https://mobbin.com/screens/9f0d2a69-0445-4c6d-a4ab-94275b5be1b7): restrained hierarchy; stacked groups were not the selected Cuadrao direction.
- [Apple lists and tables](https://developer.apple.com/design/human-interface-guidelines/lists-and-tables): clear hierarchy and grouping.

## What is interactive

Home switches balance display, accounts and activity together. Joint fixture
accounts have one identity and can appear in Personal and Household. Household
omits private fixtures. These are presentation examples, not access controls.
Add offers Household, Business, Custom and Manage spaces. New private spaces start
empty; new accounts are assigned to the selected preview space. Names are unique
including archived/deleted spaces. Management supports private rename,
archive/restore, and recoverable deletion of empty spaces. Personal stays permanent.
Account actions and reordering reuse the earlier components; reordering preserves
accounts outside the selected space. This does not add account moves or sharing.

## Verification

- XcodeBuildMCP native build/run succeeded with zero reported warnings/errors on the existing iPhone 18 Pro simulator, UUID 8AFB6084-8918-416E-9164-E21061306BEC.
- Build log: build_run_sim_2026-09-30T23-13-21-499Z_pid12375_d1f243a4.log.
- Spanish simulator journey: Personal -> Household (only two joint accounts and shared activity) -> Add -> Business -> Mi estudio -> empty Home -> add Cash with unknown balance -> Household unaffected -> Manage -> rename form -> archive -> restore and open with Cash preserved.
- Nonempty private space did not expose deletion. English Household labels and selector verified.
- Focused Swift checks executed the actual preview-model declarations: scope isolation, shared identity, reorder preservation, creation, archive fallback to Personal, duplicate names, restore, empty-space deletion/recovery, and first-use Household without automatic accounts. Checks passed. The initial sandbox run could not invoke Swift macros; the same check passed with local compiler access.
- Screenshots in this folder were captured from the same native build. Documentation and evidence additions do not change those sources.
- git diff --check passed.

## Boundaries and restart

In-memory design state resets on relaunch. No household invitations, external
sharing, permissions, backend persistence, connected totals, Plan/Search scoping,
or physical-phone acceptance is claimed. Household creation opens an empty visual
context; invitation and sharing screens remain separate design work. The populated
fixture includes two joint accounts solely to demonstrate the shared Home.
Full Dynamic Type, VoiceOver, small-device, long-name and large-space-count matrices
are not yet verified. Empty deletion was checked at model level, not a full UI journey.

Reuse scheme ArgusFoundation, bundle local.cuadrao.design and derived data
/private/tmp/cuadrao-native-design-build. Launch with --cuadrao-design --cuadrao-home
--home-populated; add --design-english for English, omit --home-populated for first
use. The existing browser mirror is http://localhost:3200/. Do not create another
simulator or derived-data directory for this canvas.
