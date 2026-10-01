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
