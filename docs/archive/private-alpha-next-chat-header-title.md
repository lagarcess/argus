# Chat Header Title & Owner-Menu Gating

Status: active slice on `claude/chat-header-ui-polish-9ebbe2` (parent:
`codex/private-alpha-next`).

## Goal

The chat header stops saying a static, centered "Conversation" and instead
shows the conversation's real name — the same backend-owned title Recents
shows — revealed with a short scramble animation when the name is first
generated. The header's three-dot owner menu (rename / pin / delete) appears
only when there is a conversation to own. The blurred top scrim is untouched.

## Why

- "Conversation" carries no information; the generated title gives the surface
  identity and matches what users see in Recents.
- Today the three-dot menu renders on the brand-new chat surface where
  rename/pin/delete have nothing to act on; the items look enabled but
  silently no-op. That reads as broken.
- The title is generated server-side after the first turn and arrives
  atomically (no token stream). A scramble reveal is the honest presentation
  of that shape: it decorates a complete string instead of faking a stream.

## Decisions (agreed)

1. One source of truth: the header reads the same client state Recents reads
   (`historyItems` → `activeHistoryChat`). No new title-generation lane, no
   second store.
2. While a conversation has no generated or user name yet
   (`title_source === "system_default"`), all surfaces show the localized
   placeholder `t("chat.new_chat")` — never the backend's internal default
   string ("New idea"), which is English-only.
3. Scramble reveal plays exactly once per naming event: when the *active*
   conversation transitions from an unnamed source to `ai_generated`. Never
   on: conversation switch, reopening old chats, user rename (instant swap —
   it is the user's own text), or poll refreshes re-delivering the same title.
4. Three-dot menu renders only when `conversationId !== null` — existence,
   not "successful turn", because a failed first turn still creates a chat the
   user must be able to rename/delete. It fades in at first send.
5. The top scrim and header geometry (`h-20`, absolute overlay) stay as they
   are.
6. Strategies view header title moves left too — one header system.
7. Browser tab title mirrors the final title only (no animation frames).

## Backend contract change

`GET /history` chat items gain `title_source` (`system_default |
ai_generated | user_renamed`), sourced from the conversation record. This is
already part of the `Conversation` schema; history items need it so the
frontend can distinguish "unnamed" from "named" without string heuristics.

Touchpoints: `HistoryItem` schema, history router (both supabase and memory
paths), `list_history_rows` select columns, `docs/API_CONTRACT.md` history
example. Non-chat items omit the field.

## Frontend behavior

### Header title

- Left-aligned in the existing header row (same `px-4 md:px-8` inset the
  actions use), `flex-1 min-w-0 truncate`, single line, current type ramp
  (17/18px semibold, 80% ink). The old centering spacer goes away.
- Renders only when the chat surface has messages (`messages.length > 0`);
  the empty "argus" hero surface keeps a bare header.
- Value: `activeHistoryChat` title when its source is `ai_generated` or
  `user_renamed`; otherwise the localized placeholder.
- Deep-link fallback: if the active conversation has messages but is not in
  the loaded history page, fetch `listConversations({ limit: 50 })` once and
  use the matching record; keep the placeholder if it is not there either.
- `document.title` mirrors the resolved title (`"<title> · argus"`, default
  `"argus"` otherwise, final strings only).

### Scramble reveal

- Trigger: previous and next header state share the same conversation id,
  next source is `ai_generated`, previous source was not `ai_generated`/
  `user_renamed`, and the text changed.
- Motion: ~700 ms, characters settle left→right with ease-out; unsettled
  characters cycle random glyphs from a quiet alphanumeric charset at
  ~55 ms per swap and render at reduced opacity. Spaces never scramble, so
  word shape stays readable.
- `prefers-reduced-motion`: no scramble — the new title fades in (~200 ms).
- Accessibility: the accessible name is the final title from the first frame
  (`sr-only` text); the animated glyphs are `aria-hidden`.
- Sidebar Recents: no scramble — the row title crossfades (remount fade keyed
  by title). One stage for the performance.

### Owner menu gating

- The three-dot button (and its menu) render only when
  `conversationId !== null`, with a short fade-in on appearance.
- Menu contents unchanged: rename, pin/unpin, delete — the only real owner
  actions (per the conversation-trust guardrail).
- Rename prefill uses the resolved display title and prefers empty input while
  the conversation is unnamed (fixes the current guard that compares against
  a string the backend never stores).

## Out of scope

- Click-to-rename on the header title (later polish).
- Streaming title generation (`title` SSE frame). The client keeps its
  existing dormant handler as the forward contract; delivery stays post-turn
  via the settle poll.
- Any change to naming itself (`schedule_artifact_naming_after_stream` and
  `maybe_generate_conversation_title` are untouched).

## Verification

- Bun unit tests for the pure logic: display-title resolution, reveal
  trigger, scramble frame generation (deterministic rng injection), rename
  prefill.
- Backend pytest: history payload carries `title_source` for chat items.
- Live browser QA (dev stack, mock auth, fixture symbols): new-chat surface
  has no three-dot; menu fades in at first send; placeholder shows during the
  first turn; scramble plays when the generated title lands; Recents and
  header always agree; rename/pin/delete still work; scrim intact; mobile
  and dark mode spot checks.
