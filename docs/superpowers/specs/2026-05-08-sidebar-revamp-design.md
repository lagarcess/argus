# Sidebar Revamp Design

Date: 2026-05-08
Status: Approved for clean-restart implementation with PR80 guardrails

## Context

Argus is a chat-first investing idea validation platform. The sidebar should help users start a new idea, resume prior thinking, and access account-level actions without pulling focus away from the active conversation.

This design keeps the current implemented sidebar look and the existing top Argus header segment. It optimizes the sidebar around continuity, search truth, and low-friction profile/settings access.

Source-of-truth alignment:

- `docs/PRODUCT.md`: conversation is the primary product surface; Recents reduce navigation friction.
- `docs/ARCHITECTURE.md`: frontend renders persisted product records; Supabase owns durable state.
- `docs/API_CONTRACT.md`: chat, search, feedback, and profile changes must stay contract-first.
- `docs/DATA_MODEL.md`: conversations support `title_source`; archived/deleted records have distinct ownership semantics.
- `.agent/designs/argus/DESIGN.md`: chat-first UX, frictionless revisit, calm motion, accessible controls, no dashboard drift.

## Goals

- Preserve the current sidebar visual identity.
- Make Recents a chat-first resume surface.
- Replace the stale sidebar search input with a centered `Search` overlay.
- Search across chats and chat-owned artifacts while displaying chats as the canonical result.
- Generate useful AI chat titles so search is meaningful.
- Move settings/profile/data/help/feedback into lower-friction profile menu overlays.
- Upgrade bug feedback to structured reporting with real guarded Supabase Storage attachments.
- Fix collapsed-sidebar icon flicker.

## Non-Goals

- Do not redesign the top Argus icon/title/collapse header segment.
- Do not build a full command palette.
- Do not make strategies, runs, or collections standalone search result rows in this phase.
- Do not revive collections as a primary sidebar surface beyond the existing feature flag.
- Do not add semantic/vector search.
- Do not implement native mobile-specific UX in this pass; web is the optimization target.
- Do not modify `src/argus/agent_runtime/**` or `tests/test_backtest_state_machine.py`.
- Do not change the live chat SSE contract, event order, or critical-path behavior in
  `src/argus/api/routers/agent.py`.
- Do not move or weaken persisted confirmation/result card hydration from
  `web/components/chat/ChatInterface.tsx`.

## Protected PR80 Boundaries

PR80 made the live conversation the primary product surface. Sidebar work must wrap
around that surface rather than refactoring through it.

Protected behavior:

- `/api/v1/chat/stream` must continue to emit canonical data-only SSE frames through
  `final` and `[DONE]`.
- `final` remains the decisive UI event for confirmation cards, result cards, result
  actions, and persisted message ids.
- `ChatInterface.tsx` continues to hydrate persisted `messages.metadata` into
  confirmation cards, result cards, latest run ids, and result actions after reload.
- Runtime thread state remains owned by the LangGraph checkpointer using
  `thread_id == conversation_id`; Supabase stores durable product records only.

Any change that violates these boundaries requires a separate chat-runtime plan.

## Sidebar Shell

The sidebar keeps its current hierarchy and look:

- Top Argus header remains unchanged.
- `New chat`, `Strategies`, optional `Collections`, and `Recents` remain in the main nav area.
- The stale search input above Settings is removed.
- Settings is replaced by a profile initials button in the lower sidebar area.

When collapsed:

- Nav icons stay in stable slots to prevent flicker during width transitions.
- Hovering/focusing an icon shows a tooltip with its title, except the profile initials button, which opens the profile menu.
- Icon outline animation happens only when hovering/focusing the icon itself, not the whole row.
- The animation is subtle, uses Argus-safe muted strokes, does not loop, and respects `prefers-reduced-motion`.
- The main Argus header segment remains unchanged.

## Recents Behavior

`Recents` has two distinct hit targets:

- Clicking the `Recents` label opens the centered `Search` overlay.
- Clicking only the Recents chevron toggles the dropdown.

The Recents dropdown:

- Shows chats only.
- Groups chats by `Today`, `Yesterday`, `Last 7 days`, and `Last 30 days`.
- Does not show runs, strategies, or collections.
- Clicking a chat row opens that conversation in the main chat surface.
- The active conversation displays a `Current` tag.
- Rows show dates as `Mon DD`, for example `May 07`.

Long press on Recents chat rows:

- Reuses the Strategies long-press action pattern.
- Uses icon actions only: `Pin`, `Rename`, `Archive`, `Delete`.
- Uses current implementation icon choices when available: `Pin`, `Edit2`, `Trash2`.
- Archive uses a cabinet, inbox, box, or archive-style lucide icon that reads as "stored away."
- Hovering/focusing an action icon shows a verb tooltip.
- Delete keeps the muted Argus danger treatment and highlights icon strokes on hover/focus.
- Keyboard focus and touch alternatives must exist; hover must not be the only access path.

## Search Overlay

The centered overlay uses the same muted blurred backdrop language as existing language/settings modals. The input placeholder is `Search` so the shell can later evolve without relabeling, but this phase is not a full command palette.

Desktop expanded view:

- Left panel: grouped chat results.
- Right panel: scrollable actual chat history preview.
- Matched terms are highlighted in the message history.
- Hovering/focusing a result row highlights the row and replaces the date with icon actions: `Rename`, `Archive`, `Delete`.
- Omni-search row hover actions do not include `Pin`.
- Hovering/focusing an action icon shows its verb tooltip.
- Bottom-left expand/collapse control uses an icon whose shape reflects the current view state.

Collapsed/narrow view:

- Uses the cleaner single-list layout from the reference.
- This is the default for mobile/narrow screens.
- The preview panel is not shown in collapsed mode.

Empty state:

- If no matches exist, show `No results found.` centered in the overlay.

## Search Result Truth

Search results are displayable chats.

Search may match:

- Conversation title.
- Conversation message bodies.
- Conversation last message preview.
- Strategy names associated with a conversation.
- Run/result titles associated with a conversation.

If a strategy or run matches, the result row is still the containing chat. The expanded preview highlights the actual matching text in the chat history where available. If the match came from strategy/run metadata that is not directly present in the message body, the preview should still open the containing chat and highlight related title/result-card text when available.

Search can include:

- Active chats.
- Older chats beyond the 30-day Recents dropdown window.
- Archived chats.
- Recently deleted chats still inside the visible recovery window.

Collections stay excluded/stale for now.

## Archived vs Recently Deleted

Archived and recently deleted chats are not redundant.

Archived chats mean the user wants durable memory out of the way. They remain searchable, recoverable, and hidden from default Recents.

Recently deleted chats mean the user intends removal but gets a recovery window. The product target is a 7-day visible recovery period:

- During the 7-day window, recently deleted chats can appear in Search and Recently Deleted.
- After the 7-day window, they disappear from user search and restore surfaces.
- They may persist in the database longer for retention or cleanup policies, but the UI must not imply instant permanent erasure unless the backend truly guarantees it.

## AI Chat Titles

Current conversations default to `New idea` with `title_source = system_default`. This weakens Recents and Search.

This pass must add AI-generated chat titles:

- Generate a title after enough user/assistant context exists, including educational
  and exploratory chats that do not produce a strategy.
- Persist the title on the conversation with `title_source = ai_generated`.
- Never overwrite conversations with `title_source = user_renamed`.
- Keep titles short, plain, and useful for recall.
- Match the user language where possible.
- Use the existing title source model instead of adding a parallel naming field.
- Title generation is a recall enhancement and must never block, delay, or precede
  the current turn's canonical `final` event. If title generation fails, the chat
  turn must still complete normally.

## Profile Menu And Settings Migration

The lower sidebar settings button becomes a profile initials button.

Clicking the profile button opens a menu in this order:

- Profile, no chevron.
- Data, chevron.
- Settings, chevron.
- Help, chevron.
- Feedback, chevron.

Chevron rows:

- Show a submenu on hover where appropriate.
- Open a centered muted blurred overlay on click.

Functional destinations:

- Data: Archived Chats, Recently Deleted.
- Settings: Appearance, Language, Security.
- Help: Terms of Service, Privacy Policy.
- Feedback: Report a Bug, Request a Feature, General Feedback.

Implementation notes:

- Appearance and Language keep existing functionality.
- Archived Chats and Recently Deleted keep existing restore functionality, with the 7-day visible recovery behavior implemented for deleted chats.
- Security, Terms of Service, and Privacy Policy remain deferred entries unless existing product content is available; code must mark them as inert or disabled rather than silently pretending they are complete.
- This refactors the existing Settings page into lower-friction overlays instead of keeping a separate page that pulls the user away from the conversation.

## Structured Feedback And Attachments

Report a Bug is upgraded to a structured form:

- Title, required.
- Steps to reproduce.
- Expected outcome.
- Actual outcome.
- Attachments.
- Screenshot control that captures the current visible app state as a PNG attachment. If capture fails, the control must show a clear error instead of silently doing nothing.
- Consent checkbox.
- Cancel and Submit actions.
- Character counts preserved for bounded text fields.

Uploads:

- Use real Supabase Storage uploads.
- Store attachment metadata in `feedback.context.attachments`.
- Reject invalid files before upload.
- Use a strict allowlist of safe types.
- Enforce max file size.
- Enforce max file count.
- Reject empty files.
- Reject unknown MIME types/extensions.

Initial guardrail recommendation:

- Max files: 3.
- Max size per file: 5 MB.
- Allowed image types: `image/png`, `image/jpeg`, `image/webp`.
- Allowed text diagnostics: `text/plain`, `text/x-log` when detectable.
- Defer PDFs unless product explicitly accepts the extra risk.

## Component Boundaries

Extract sidebar shell concerns only. Do not move or modify live chat streaming,
message hydration, confirmation/result card rendering, or result action hydration in
`ChatInterface.tsx` during this pass.

Proposed frontend units:

- `ChatSidebar`: shell, collapse state, nav buttons, Recents entry, profile button.
- `SidebarNavButton`: icon slot, tooltip, active state, icon-only outline animation.
- `RecentChatsDropdown`: chat-only grouped list.
- `ChatRowActions`: hover/focus and long-press action layer.
- `SearchOverlay`: centered blurred overlay with expanded/collapsed layouts.
- `SearchResultsList`: grouped displayable chat results.
- `ChatPreviewPanel`: scrollable message-history preview and highlighting, backed by
  a search-only adapter that does not import or depend on live chat hydration.
- `ProfileMenu`: initials avatar menu.
- `ProfileMenuSubmenu`: hover submenu behavior.
- `SettingsOverlayPanel`: lower-friction overlays for settings/data/help.
- `StructuredFeedbackDialog`: bug/feature/general feedback forms and upload state.

Search and feedback API changes must remain contract-first and thin-router aligned.
The live chat stream contract is protected and must remain unchanged in this
sidebar pass.

## Data And API Requirements

Contract additions to define before implementation:

- Search response must return chat-centric results with match metadata.
- Search preview must render persisted message content and metadata through a
  search-only adapter. The live chat hydration path must remain untouched.
- Strategy/run matches must include the containing `conversation_id`.
- Deleted chat visibility must account for a 7-day recovery window.
- Feedback attachment metadata shape must be documented before implementation.
- Title generation must be implemented outside the chat stream critical path and must
  not emit a title event before `final`.

Candidate response shape for planning:

```json
{
  "items": [
    {
      "type": "chat",
      "id": "conversation-id",
      "title": "Tesla dip idea",
      "title_source": "ai_generated",
      "status": "active",
      "matched_sources": ["message", "run"],
      "matched_ranges": [],
      "updated_at": "2026-05-08T00:00:00Z"
    }
  ],
  "next_cursor": null
}
```

The final shape must be defined in `docs/API_CONTRACT.md` during implementation planning.

## Accessibility

- All icon-only buttons need accessible labels.
- Tooltips are supplemental; actions must be available through focus and touch.
- Icon outline animation must respect `prefers-reduced-motion`.
- Hover row actions must also appear on keyboard focus.
- Search overlay must trap focus while open and close on Escape.
- Long-press actions must have a tap/click alternative for non-hover users.
- Destructive actions need clear visual distinction and confirmation where product risk warrants it.

## Testing Plan

Required tests:

- Collapsed sidebar keeps stable icon positions without flicker.
- Top Argus header collapse/expand behavior is unchanged.
- Collapsed icon hover/focus shows tooltip and animates only the icon outline.
- Recents chevron toggles dropdown without opening Search.
- Recents label opens Search without toggling dropdown.
- Recents dropdown only shows chats from the last 30 days.
- Recents long press opens icon actions: pin, rename, archive, delete.
- Omni-search row hover/focus shows rename, archive, delete only.
- Current tag follows the active conversation.
- AI chat title generation updates `system_default` conversations and never overwrites `user_renamed`.
- Search returns containing chats for message, strategy, and run matches.
- Expanded Search preview renders scrollable actual chat history with highlighted terms.
- Archived chats are searchable and recoverable.
- Recently deleted chats are searchable and recoverable only during the 7-day recovery window.
- Feedback bug form validates required title, consent, character counts, file size, file count, file type, and empty-file rejection.
- Supabase attachment metadata persists with the feedback record after upload.
- A normal chat turn always reaches `final` and `[DONE]`, even when AI title
  generation fails.
- Confirmation cards render from final payloads and hydrate from message metadata.
- Result cards render from final payloads and hydrate from message metadata with
  result actions carrying canonical run/conversation context.
- Search preview does not require moving live chat hydration out of the chat surface.

Verification should include focused frontend tests plus API tests for search/title/feedback contract behavior. Browser visual QA should cover desktop expanded overlay, collapsed overlay, collapsed sidebar, and narrow/mobile layout.

## Open Implementation Decisions

- Exact archive icon choice from lucide after checking available icons.
- Supabase Storage upload uses a backend-mediated upload endpoint for this pass; no
  service-role credential is exposed to the browser.
- Search response shape and pagination cursor behavior are documented in
  `docs/API_CONTRACT.md`.
- Deleted chat 7-day visibility is derived from `deleted_at`; no new database column
  is required.
- Screenshot capture uses a lazy-loaded browser-only dependency so initial chat load
  does not pay for screenshot code.

## Acceptance Criteria

- A user can collapse the sidebar without icon flicker.
- A user can open recent chats quickly from the Recents chevron dropdown.
- A user can search prior chat work, including older and archived chats, from a centered overlay.
- A user sees actual scrollable chat history in expanded search preview with highlighted terms.
- A user can understand why strategy/run-related content matched because it opens the containing chat.
- A user can rename/archive/delete from Search result hover/focus actions.
- A user can pin/rename/archive/delete Recents rows from the long-press action pattern.
- A user sees meaningful AI-generated chat titles instead of repeated `New idea` rows.
- A user can access profile/data/settings/help/feedback without leaving the chat surface.
- A user can submit a structured bug report with safe uploaded attachments.
