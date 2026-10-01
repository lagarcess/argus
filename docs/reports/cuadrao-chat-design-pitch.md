# Cuadrao chat: reference study and proposal

**Follow-up owner:** [main roadmap, C04](../specs/argus-execution-board.md#cuadrao-design-dispositions).
This is dated research/iteration history, not the current implementation queue;
subsequent preview work and remaining delivery gaps are distinguished there.

September 30, 2026. Research and pitch only. Profile UI is paused at `425ee881d`.
This document does not approve a new backend capability or implement chat.

## Recommendation

A quiet, readable conversation with a capable composer. Preserve the existing
chat header, temporary mode, history and capture decisions. Use Cuadrao's typography,
provisional pine accent and approved icon language throughout. The main canvas
should feel useful immediately, with richer controls revealed in context.

## References actually inspected

| Reference | Observation | Proposed use in Cuadrao |
| --- | --- | --- |
| [Claude file-input flow](https://mobbin.com/flows/000b65e0-53df-41b1-87f3-863a6ade9165) | Attachment choices; removable PDF chip before send; keyboard under composer; sent file remains attached to the user turn; stop control during response; readable unboxed assistant prose and return-to-latest arrow | Stage files visibly, retain provenance beside the question, give the answer the main reading area. Preserve our existing inline attachment tray rather than automatically copying Claude's sheet. |
| [Claude chat search](https://mobbin.com/flows/a2e795ec-b560-43be-8496-e1b98cf5495a) | Quiet title/time rows; explicit New chat; search narrows the same list | Clear, searchable history with the locked pinned/recent and empty/no-result behavior. Do not move search to the bottom merely to match Claude. |
| [Perplexity sources](https://mobbin.com/flows/c4f2c6a3-015c-44be-b412-88390d5ec94e) | Inline citation chips, source count, source sheet with numbered titles/domains, separate follow-up rows | Evidence stays within reach without occupying the whole answer. Preserve our source dates and source-owned links. Omit its browser promotion. |
| [WhatsApp document flow](https://mobbin.com/flows/8649713d-4a71-47d8-b2f2-905441d264a2) | Labeled attachment choices; native Files picker; sent document has preview, name, metadata and caption | Familiar file selection and clear attachment identity. Avoid its unrelated location/contact/poll actions and message wallpaper. |
| [ChatGPT temporary chat](https://mobbin.com/screens/a2e349cb-a422-4757-8a3c-d34cd5aecdd3) | Distinct top-right temporary control and explanation on an otherwise quiet canvas | Keep our already-approved dashed chat glyph and context choice. Do not copy ChatGPT's retention or training promises. |
| [ChatGPT Codex conversation](https://mobbin.com/flows/5e309eff-eb81-4573-bcd0-df2b7f8b8f50) | User bubble, open assistant response, running/stop state and compact follow-up composer | Useful comparison for state legibility only. Its computer/model/tool selectors and technical execution logs do not fit this Cuadrao pitch. |

Coverage: inspected connector previews for these flows. Claude's five-frame
attachment sequence was also inspected horizontally in the website to cover the
unsampled pre-send and in-progress frames. Both Claude search frames and all three
Perplexity source frames were seen. WhatsApp and the seven-frame Codex flow were
sampled, not exhaustively reviewed. Static frames do not prove animation timing.

Mobbin website metadata for the inspected Claude capture: 4.83 from 16 ratings,
Productivity/AI, 56 flows and 158 UI elements. These are Mobbin observations, not
App Store ratings or proof of best UX. The UI Elements > Text Field filter returned
two authentication/project fields, not its composer: taxonomy coverage is incomplete,
so the flow sequence was the stronger source. Related-app discovery included
Perplexity. Selection is based on the task, not on rating alone.

Rejected mismatches: the first ChatGPT query returned project Chats, not the
ordinary conversation. A Claude message-action query returned project rename/archive/
delete; it does not support claims about message menus. No message-action detail
is attributed to that result. No Mobbin artwork is copied into the proposal.

## Existing Cuadrao behavior to preserve

Read `.agent/designs/argus/DESIGN.md` sections 11, 12 and the September 28 mobile
lock, plus the original `chat-shell.js`, `chat-mode.js`, `composer-preview.js` and
`mobile-lock/chat.png` in the local HTML study.

- Header by state: empty regular has Recents left and temporary entry right;
  active regular adds New on the left and Share/More on the right; temporary
  retains New regular left and temporary settings right. Reserve slots so icons
  do not jump. The provisional assistant mark is not the retired Argus logo.
- Existing bottom navigation and its approved behavior remain the baseline.
- Composer keeps separate add, dictation and voice affordances; send appears when
  a draft or attachment is ready. Dictation and spoken conversation are different.
- Inline tray offers receipt/photo/file. Draft text and removable attachments stay
  together. Suggestions collapse with tray expansion; preserve stable tap targets.
- Chats supports search, pinned/recent, rename, unread state, archive/restore and
  deletion/recovery presentation. Search opens the same conversation identity.
- Temporary mode preserves the regular draft, exposes the existing context choice,
  locks that choice after starting and confirms departure when content exists.
  These are design semantics; retention and production privacy require real contracts.
- Answers retain calculation/research/simulation artifacts, sources and relevant
  follow-up rows. Clarification choices and persistent discovery choices have
  different lifecycles. An active card owns its actions.
- Receipt/financial proposals require review before recording. A message is not a
  saved financial record. Existing recording owner and permissions remain authoritative.

## Proposed screen and flow

1. **Start:** small Cuadrao mark, one Spanish greeting such as “¿Qué vemos hoy?”,
   restrained starter suggestions and the existing composer. No redundant chat title
   or dashboard inside the conversation. Final greeting is proposed, not locked.
2. **Compose:** stable rounded input, + on the left, distinct dictation/voice/send
   states on the right. Attachments sit above the text and can be removed. Native
   keyboard movement should keep the draft readable and controls reachable.
3. **Read:** a subdued user bubble; open assistant text with deliberate heading,
   paragraph and list rhythm. Pine is an accent for actions, not a large response
   background. No repeated robot avatars or boxed treatment for every paragraph.
4. **Inspect or act:** source counts open source details; computed results expand
   their inputs; recording proposals lead to the established review controls.
   Returning closes the detail and preserves reading position and draft.
5. **Continue:** history and temporary mode follow the locked header behavior.
   Message-level copy/feedback/more should be discoverable, with optional long-press
   shortcuts, not long-press-only actions. Full actions need a dedicated reference
   and contract check before implementation; do not import unsupported Retry/Edit.

## Platform and acceptance requirements

[Apple generative-AI guidance](https://developer.apple.com/design/human-interface-guidelines/generative-ai)
asks for clear AI identity, a considered loading experience and feedback.
[Apple context menus](https://developer.apple.com/design/human-interface-guidelines/context-menus)
requires those actions to be available in the main interface as well. Apply these
through clear assistant context, reachable feedback and visible action entry points.

Any later UI pass should be reviewed as a coherent flow: empty, keyboard open,
attachment staged, response in progress, completed answer, source/result detail,
history/reopen, temporary mode and recovery. Include long Spanish content, English,
Dynamic Type, VoiceOver, reduced motion, light/dark and the physical phone.

Server stages own live progress. Stop/retry only appear as working actions where
existing contracts support them; preview states cannot imply real cancellation.
Preserve drafts on failure and show a reachable recovery action. Live evidence,
financial writes, memory changes, ingestion and voice connections remain outside
this design-only assignment. No fake percentage/progress, permission claims or
automatic memory-saving promises.

## Remaining research limits

This pitch is supported by specific screens, not an exhaustive Mobbin audit.
Message actions, error states, live scrolling/keyboard motion and native financial
artifact rendering require focused verification when implementing. No claim of
matching a reference app's latest installed release or measured motion is made.
