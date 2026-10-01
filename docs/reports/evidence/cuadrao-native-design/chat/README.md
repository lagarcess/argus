# Native chat proposal

September 30, 2026. Founder requested trying the researched chat proposal.
Profile is untouched at its unfinished checkpoint. This is local design state,
not a connected assistant, ingestion, memory or financial-write implementation.

## Included

- Spanish-first welcome, starter examples, stable header slots, expandable inline
  attachment tray, removable file chips, growing draft input and voice/dictation
  presentation entry points.
- Open assistant typography, restrained user bubbles, an illustrative calculation
  card and its assumptions, and an explanation of general-knowledge provenance.
- Searchable history with pinned/unread/archive/deleted presentation, rename,
  restore, new chat and temporary-context controls.
- One root-owned observable chat preview store feeds history and Search. Search
  opens the existing conversation rather than copying its transcript.
- Temporary mode suspends the regular draft and asks before leaving with content.
  Actual model, document capture and recording behavior remain with existing owners.
- Explicit preview-state chooser for waiting/failure. No timer pretends to execute
  a request. Arbitrary typed messages receive an honest disconnected-preview reply.

## Verification

- Simulator build passed with zero reported diagnostics; iPhone build passed.
  Generic iOS destination was rejected; the existing explicit paired-iPhone
  destination succeeded. Existing simulator and DerivedData were reused.
- Browser-driven simulator review: welcome and composer/nav separation; sample
  answer and calculation detail; file tray, stage and send; history; new chat;
  dictation sample into a temporary draft; exit confirmation and return to Home;
  Search > Chats reopened the same calculation conversation.
- Initial composer/nav overlap was corrected before acceptance captures.
- Text entry reached the native field. The simulator's English hardware keyboard
  autocorrected the Spanish test phrase, so exact Spanish typing/software keyboard
  acceptance is not claimed. Full phone touch, English, Dynamic Type, VoiceOver,
  reduced-motion and dark-mode matrices remain open.
- welcome.jpg is from the final simulator build. answer.jpg was captured before
  the final attachment-removal accessibility-label-only adjustment; the answer
  layout and calculation code were unchanged and visually revalidated.
- No model/API calls, financial writes, Profile changes, new simulator/cache,
  merge or deployment.

## Still open

This is a first native chat design pass, not the full assistant acceptance.
Live streaming/cancellation/retry, complete contextual artifacts and review flows,
real sources, memory controls, file opening/capture, voice connection, share-link
review and broader message actions still need their existing contracts connected.
The source explanation explicitly says no external research occurred; no fake
financial citations are supplied. Recovery and share presentation are previews.

## Founder icon correction

The temporary-chat entry now uses the exact vector path from HTML chat-mode.js,
not an SF bubble with a dotted circle. The same asset renders its hero/status.
The existing time-aware/typed greeting logic remains required for connection;
the native greeting is currently static and does not replace that behavior.


## Temporary chat adaptation, September 30

Reviewed the actual HTML `chat-mode.js`, `chat-shell.js`, composer behavior and
MVEE temporary-chat contract. Mobbin references visually inspected:
[ChatGPT: Switching to Temporary Chat](https://mobbin.com/flows/160a1a14-bf8b-4f51-b34c-b1b567131bcc)
and [Claude: Switching to incognito chat](https://mobbin.com/flows/ded64e16-69be-4cf6-ba85-b06cd13d7c68).
Borrowed short icon-led explanations and quiet mode presentation. Kept Cuadrao's
one-tap entry, naming, explicit optional context, exit guard and regular-draft
restoration. Did not import other products' retention or model-training promises.

| Interaction | Native adaptation |
| --- | --- |
| Enter temporary | One tap; context off; previous thread, draft and attachments suspended. |
| Context choice | Editable before first send; model owns the lock thereafter. Active status shows the chosen context. |
| Return to regular | Restores the suspended thread and draft. |
| New regular chat | Ends temporary mode and opens a blank regular chat. |
| Open history | Ends temporary mode and opens the selected thread; deleted restoration occurs only after confirmation. |
| Leave for another tab | Uses the same content check and end operation. |
| Discard guard | Sent messages, nonblank draft or attachment require confirmation; whitespace alone does not. Cancel keeps the current state. |
| Background app switch | No background-discard handler is added. |
| Details | Expandable explanation covers leaving, previous drafts and preview/retention limits. |

Founder explicitly kept the attachment chooser **below** the composer controls.
Tradeoff: closer to the + button and thumb, but uses lower-screen space and moves
the composer upward when expanded. Opening it dismisses the keyboard; focusing
the draft closes it. Selected attachment chips stay above the text for review.
This is an intentional native variation from HTML's upper tray.

Verification: final simulator and iPhone builds passed; the final iPhone build
is installed under the separate `Cuadrao Preview` identity. `python3 ios/DesignPreviewTests/run_temporary_chat.py`
passes against the actual native model and actual reference fixtures in Spanish
and English: whitespace, attachment-only content, context lock, history exclusion,
regular draft/attachment restoration, new regular chat and opening history.
Uses the existing build cache and cleans its temporary test executable.

The iPhone 18 Pro simulator was concurrently running #760's FinancialLoopUITests
and repeatedly returned to that app. Founder confirmed simulator
`8AFB6084-8918-416E-9164-E21061306BEC` remains assigned to this design lane;
#760's verification is being moved elsewhere. Do not interact with or relaunch
this simulator until it is released. Final visual/keyboard/discard-dialog
acceptance is pending and must be repeated after release. Prior screenshots do
not certify this change. No new simulator, backend behavior, retention policy
or Profile changes.

## New-chat icon correction

Founder selected the original HTML bubble-plus icon over square-and-pencil.
The exact vector now serves both the header (including “Nuevo chat normal” from
temporary mode) and the history sheet. Existing exit confirmation and new-chat
behavior are unchanged. Simulator visual checks remain pending its release.
