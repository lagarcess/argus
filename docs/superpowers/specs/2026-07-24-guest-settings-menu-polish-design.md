# Guest Settings Menu Polish

## Goal

Make the guest gear menu quieter and more deliberate while preserving the
existing guest policy and the original landing-page language behavior.

The reference is the compact settings popover supplied by the founder:

- an icon-only theme selector at the top;
- a single Language entry point;
- a single Feedback entry point;
- a separate centered language modal.

This is a presentation correction to Guest Experience Block 2. It does not
start account conversion or any other Block 3 work.

## Approved Interaction

### Gear and popover

- Keep the existing 44-by-44-pixel gear target and current header position.
- Render the gear icon at a smaller, quieter visual weight.
- Remove the `Theme` heading.
- Place Light, Dark, and System in one compact icon-only segmented control.
- Use the existing Argus Lucide icons at a smaller size.
- Show the selected theme with a soft neutral tile rather than a high-contrast
  control.
- Keep exactly two menu rows below the theme control:
  - Language
  - Feedback
- Keep the current Sign in action separate from the popover.
- Do not expose public Create account while public-account access is disabled.

### Language modal

- Language closes the popover and opens the shared centered language modal used
  by the existing settings surfaces.
- The modal retains search, enabled-language filtering, the current-language
  checkmark, outside-click dismissal, keyboard focus, and Escape dismissal.
- Closing the modal returns focus to the gear trigger because the Language row
  is no longer mounted after the popover closes.
- Selecting a language applies it immediately and closes the modal.

### Feedback

- Feedback closes the popover and opens the existing feedback dialog.
- Feedback taxonomy, persistence, telemetry, and quota behavior remain
  unchanged.

## Language Persistence Truth

The original landing settings behavior has three owners:

1. `i18n.changeLanguage` updates the current browser preference immediately.
2. Permanent authenticated profiles are updated through `PATCH /me`.
3. New signup requests include the currently selected browser language.

After login to an existing permanent account, the registered profile remains
authoritative and may replace the browser preference during hydration.

Guest policy remains unchanged:

- a guest is a verified anonymous Supabase Auth user;
- guest `PATCH /me` remains forbidden;
- the selected language persists in the browser through the existing i18next
  storage behavior;
- the menu does not add a failing guest profile write;
- future guest-to-account conversion may explicitly transfer this browser
  preference, but that handoff belongs to Block 3.

The shared language modal therefore accepts an explicit persistence policy:

- registered/landing use keeps the current permanent-profile persistence
  behavior;
- guest use changes browser language without writing the guest profile.

## Component Boundaries

- `GuestSettingsMenu` owns popover open state, theme selection, the Language
  entry point, Feedback entry, and focus restoration.
- `LanguageModal` remains the shared centered language surface and accepts the
  persistence policy needed by the caller.
- `GuestLegalFooter` remains the sole visible owner of temporary-chat expiry.
- `ChatSidebar` has no guest-expiry presentation or expiry prop.
- `GuestEmptyStateIntro` owns only the existing headline.
- `GuestHeader`, the chat runtime, account context, and feedback owners do not
  change.

No new settings framework, icon package, route, API endpoint, or profile policy
is introduced.

## Empty-State Hierarchy Correction

This same pass makes one narrow guest empty-state correction:

- Remove temporary-chat expiry from the sidebar entirely.
- Keep one temporary-chat notice beneath the composer in both the empty and
  populated conversation layouts.
- Visible copy uses a localized date only:
  - English: `Temporary chat · available until {localized date}`
  - Spanish: `Chat temporal · disponible hasta {localized date}`
- Preserve the exact server timestamp in the notice's semantic `time` element
  and accessible metadata. Do not change its source, timezone, or expiry
  behavior.
- Remove the explanatory paragraph beneath the guest headline.
- Keep the centered Argus wordmark and existing guest headline.
- Give the guest empty composer its own shorter localized placeholder:
  - English: `What do you want to test?`
  - Spanish: `¿Qué quieres probar?`
- Do not change the registered empty-composer placeholder.
- Keep starter-chip labels, typed values, and `handleSend` ownership unchanged.
- Keep pre-message Terms/Privacy copy and post-message safety/legal copy
  unchanged.

## Responsive and Accessibility Requirements

- The popover stays fully visible on desktop and 390-pixel mobile viewports.
- The sole temporary notice stays beneath the composer with the sidebar
  expanded or collapsed.
- Theme buttons and menu rows retain at least 44-pixel targets.
- Icon-only theme buttons have localized accessible names and pressed state.
- The gear exposes menu expanded state.
- Escape closes the popover or modal.
- Outside click closes the active surface.
- Focus remains visible and returns to the initiating control.
- Light, dark, English, and Spanish states remain supported.

## Error Handling

- Theme changes are immediate and browser-owned.
- Guest language changes do not call `PATCH /me`.
- Registered language persistence keeps the current best-effort behavior.
- Feedback errors remain owned by the existing feedback dialog.
- No UI state fabricates a successful account conversion or profile write.

## Test Strategy

Red-first tests will prove:

- no Theme heading is rendered;
- the three existing icons remain in one segmented row;
- only Language and Feedback appear as menu rows;
- Language opens the shared centered modal;
- guest selection changes i18n without `PATCH /me`;
- registered/default modal use retains `PATCH /me`;
- Escape and outside click close the modal and restore focus;
- the sidebar contains no temporary notice or expiry prop;
- the composer area contains exactly one localized temporary notice before and
  after the first message;
- guest empty state retains its wordmark, headline, and starter actions while
  removing the explanatory paragraph;
- the guest empty placeholder uses the approved short English and Spanish copy;
- theme, feedback, Sign in, English/Spanish, and 44-pixel target behavior remain
  intact.

Focused unit/source-contract tests will run before the full frontend suite.
The live browser will then verify the open popover and centered language modal
at desktop and 390-pixel mobile sizes, including console health.

## Scope Exclusions

- No guest conversion modal or ownership transfer.
- No signup/login behavior changes.
- No public-account enablement.
- No onboarding changes.
- No backend, database, RLS, runtime, prompt, provider, or settlement changes.
- No production or hosted configuration changes.
