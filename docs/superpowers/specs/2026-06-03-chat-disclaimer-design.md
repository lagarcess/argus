# Chat Disclaimer Design

## Goal

Argus should show a short educational/financial disclaimer after a conversation has actually begun, without adding noise to the cold-start chat screen.

## Approved Behavior

- Cold-start `/chat` with no visible messages and no send in flight does not show the disclaimer.
- The disclaimer appears as soon as the first real turn is sent, regardless of origin:
  - typed composer submit
  - prompt/example pill submit
  - retry or regenerated first-turn flow
  - any future first-turn entry point
- The disclaimer remains visible for the rest of that conversation.
- Reloading a hydrated conversation with visible messages shows the disclaimer.
- Empty, stale, deleted, or failed conversation links do not show the disclaimer unless visible messages hydrate successfully.
- Onboarding is deferred; disclaimer behavior supersedes onboarding.

## Copy

The copy should be localizable through the existing frontend i18n path:

```text
Argus can make mistakes. For education only. Not financial advice.
```

## Visibility Rule

Use derived conversation state instead of storing a separate disclaimer flag.

The intended rule is:

```text
showDisclaimer = visibleMessages.length > 0 || firstTurnSendIsInFlight
```

This keeps behavior tied to the actual chat surface and avoids stale per-conversation state.

## Visual Treatment

- Place the disclaimer directly below the composer, centered in the same max-width column.
- Use the default body/UI font, Inter.
- Do not use the display font, Space Grotesk.
- Use regular weight, normal letter spacing, and a small readable size around `13px`.
- Use muted theme-aware text, such as `text-black/40 dark:text-white/40` or the closest existing token.
- Do not use an icon, border, card, pill, shadow, warning color, or legal-banner styling.
- The text should wrap cleanly on mobile without overlapping composer controls or following content.

## Testing

Focused frontend tests should cover:

- cold-start chat hides the disclaimer
- first send shows the disclaimer immediately, including while the response is streaming
- hydrated conversations with visible messages show the disclaimer after reload
- empty/stale/deleted conversation hydration does not force the disclaimer visible
- the rendered element uses theme-aware muted text treatment instead of hardcoded light-mode styling

## Non-Goals

- No backend schema or API changes.
- No persisted disclaimer flag.
- No onboarding changes.
- No new warning banner, modal, or legal acknowledgement flow.

## Success Criteria

The cold-start chat stays clean. Once a user starts a conversation, Argus displays a quiet, appearance-aware disclaimer that persists with that conversation and matches the product's existing typography system.
