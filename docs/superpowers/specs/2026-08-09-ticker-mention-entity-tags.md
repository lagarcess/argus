# Exact `@`-mention entity tags

## Why

Selected assets and indicators should keep their identity as a user moves from
the composer to a submitted turn and then to the existing strategy cards. Today
that identity is expressed as inline color, and it is lost after a reload. A
small typed tag makes the selected fact easy to scan without changing what the
user wrote or what Argus interprets.

This is a chat-first trust slice: the visible affordance follows the user's
selection, while the immutable message text remains the source for recall and
interpretation.

## Locked decisions

- Start the worker branch from `01044cda` and target
  `codex/private-alpha-next`. The current fetched integration ref at lane start
  is `98681a8`; reconcile it one-way before final verification.
- Commit this specification before implementation. Deliver one normal worker
  PR; the founder retains merge authority.
- Add optional `ChatMention.message_range: { start, end }` to the web and chat
  API types. It is a UTF-16 display span into the final serialized `message`.
- The composer calculates each selected token's exact span after applying its
  existing serialization and whitespace normalization. Repeated text is
  disambiguated by position, not text matching.
- Request admission persists a range only when it is a finite ordered span in
  bounds and `message.slice(start, end) === insert_text`. A malformed or stale
  range is omitted from persisted metadata; it never rejects, rewrites, or
  changes the turn.
- `message_range` is rendering provenance only. It does not enter
  `ResolutionProvenance`, LangGraph input, provider resolution, execution
  state, message content, or Omnisearch indexing/query/ranking.
- Create one shared entity-token primitive. Assets use a quiet neutral outlined
  tag; indicators use a restrained indigo outlined tag. Confirmation and result
  cards use the same asset tag treatment.
- In the composer only, a quiet focus ring appears when a collapsed caret is
  directly beside a token. There is no visible delete affordance, hover-only
  control, or "Show focus" control. Existing atomic Backspace behavior stays
  intact.
- Submitted user turns render exact stored ranges whenever every stored range
  is valid. Older or malformed metadata uses the existing safe best-effort
  matching, upgraded to the new tag appearance.
- Hydrate `metadata.mentions` into user messages so reload, Recents, and
  conversation switching retain tags.

## Explicit non-goals

- No feature flag, database migration, provider change, LLM/interpreter change,
  runtime routing change, or Omnisearch change.
- No change to user-entered message bytes, token ordering, resolution behavior,
  card data shape, or assistant copy.
- No indicator additions to existing asset-only confirmation/result card data.
- No generalized annotation framework, text editor rewrite, or authoring
  controls beyond the current composer selection and Backspace semantics.

## API and data contract

`mentions[].message_range` is an optional durable display range:

```json
{
  "start": 17,
  "end": 21
}
```

It points to the selected `insert_text` in the exact final `message` string.
The request boundary sanitizes it before putting it in `messages.metadata`.
Missing or invalid ranges retain legacy rendering behavior. The message itself
is unchanged, so user-message search and all existing metadata compatibility
remain intact.

`docs/API_CONTRACT.md` and `docs/DATA_MODEL.md` will document the additive
field and its display-only boundary in the implementation commit.

## Execution plan

1. Write failing unit tests for serialized ranges, repeated text, whitespace
   normalization, exact transcript rendering, malformed metadata, legacy
   fallback, and typed token variants.
2. Add focused shared modules for range calculation, transcript token pieces,
   and tag styling; wire the composer, hydrated user messages, and existing
   asset-card rows to them without overgrowing watched files.
3. Add the additive API schema and admission-only sanitization. Prove valid
   ranges persist, invalid ranges are stripped, message bytes remain unchanged,
   and `ResolutionProvenance` remains unchanged.
4. Add mocked Playwright coverage: select an asset and indicator, send, reload,
   and confirm only the selected occurrences appear as tags.
5. Capture exact-head EN and es-419 screenshots at desktop and mobile widths in
   `docs/reports/evidence/ticker-mention-tokens/`.
6. Re-fetch and reconcile current integration one-way if it advanced; audit any
   semantic overlap. Run focused Bun and pytest checks, the unchanged
   Omnisearch user-message recall test, Playwright, lint, build, and
   `scripts/check_modularity_budget.py` against the reconciled merge tree.

## Acceptance gates

- New selections persist correct exact ranges without changing the serialized
  message text.
- Only the selected duplicate occurrence is tagged after send and reload.
- Asset and indicator tags remain visibly distinct and keyboard-focused tokens
  have a quiet composer-only ring.
- Old or malformed metadata renders safely through legacy matching with the new
  tag style.
- Confirmation and result asset rows match the shared neutral tag treatment.
- English and es-419 desktop/mobile browser evidence is committed at the exact
  PR head.

## Stop conditions

Stop and return to the founder before proceeding if the solution requires
changing message text, Omnisearch's query/index path, runtime interpretation,
provider behavior, a database migration, or a user-visible semantic change
beyond typed mention display.
