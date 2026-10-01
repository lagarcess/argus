# Home and Household first-use design — September 30, 2026

Native SwiftUI canvas only, using in-memory sample state. Reuses the existing
Cuadrao simulator, bundle and build cache. No messages are sent, accounts shared
remotely, or financial/permission contracts implemented.

## Try it

Open the existing simulator mirror at http://localhost:3200/.
First-use Home offers Añadir cuenta. Space + → Hogar → Crear Hogar opens an empty
Household. The original name-entry invitation mock is superseded by the
[native invitation-link preview](../invitation-link/README.md). It now uses the
system share sheet, followed by an explicitly labelled recipient preview.

Long-press the Cuadrao brand to switch between first use, populated Home and a
joined household with no shared accounts. These preview switches reset sample
accounts. Data resets on app relaunch; saved Home section order is retained.

Launch the existing local.cuadrao.design bundle with --cuadrao-design
--cuadrao-home, omitting --home-populated. Add --design-english for English.
Simulator: 8AFB6084-8918-416E-9164-E21061306BEC.
Derived data: /private/tmp/cuadrao-native-design-build.

## Inspected references

- [Monarch empty transactions](https://mobbin.com/screens/0af4ad84-9be7-4708-a0bf-2f3695ecf1da): explains missing content and next action. We omit its empty charts.
- [Splitwise adding a member](https://mobbin.com/flows/9b15f463-36ad-4752-9ccc-aec98127fa83): invitation emphasis changes after someone joins.
- [Superlist empty team](https://mobbin.com/screens/20c766b0-bed3-4dab-9e4e-5061ec393bc8): shared context with explicit privacy explanation.

Cuadrao's wording and four-state composition are design proposals, not copied
translations or claims about these apps' latest versions.

## Verification

Build succeeded with no reported warnings/errors. Final build log:
`build_run_sim_2026-10-01T00-01-24-389Z_pid12375_4103a28b.log` (UTC filename).
The only source edit after that build corrects whitespace indentation.

Native simulator checks:
- Empty Personal has one Add account action, no balance total or empty feed sections.
- + → Hogar introduction → Create returns to Household with invitation and joint-account choices.
- Empty invitation name disables preparation; Alex enables it.
- Pending invitation is visible on Home; cancellation confirmation restores the invitation action.
- Preparing again and simulating acceptance changes Home to joined, with no shared accounts.
- Switching to Personal retains its separate empty state.
- Adding personal cash with a blank balance transitions to account/overview sections showing an unknown balance as a dash.
- Switching back to Household still shows no shared accounts: no implicit sharing.
- English first-use Home visually inspected; Spanish create/pending/joined screens visually inspected.
- git diff --check passes.

Screenshots in this folder capture those visible states. Spanish captures remain
applicable across the final indentation-only change. No full VoiceOver, larger
text, small-device or physical-phone matrix was run in this pass.

## Still open

This records the original first-use proposal, not the complete household flow.
Invitation screenshots and checks below are historical; see the invitation-link
continuation for the current sender and recipient UI.
Invitation delivery/contact selection, recipient acceptance screen, expired or
revoked invitations, existing-account sharing consent/permissions, member removal
and leaving remain to design. Invitation name/preparation and simulated acceptance
are preview controls, not a proposed production delivery mechanism.
