# Profile and feedback inheritance — disposable UI study

Current accepted baseline: [APPROVED-BASELINE.md](APPROVED-BASELINE.md). The sections below retain the detailed inheritance and iteration record; later explicit refinements supersede earlier experiments.

Reviewed 2026-09-26 against the local Argus integration-derived checkout. This is a source comparison, not a claim that every feature flag is enabled on the deployed site. The production browser was signed out; no authenticated production actions were exercised.

## Inherited

- `web/components/sidebar/ChatSidebar.tsx` / `SidebarNavButton.tsx`: Lucide User trigger, 20px glyph, 44px target. The demo previously used a different hand-drawn glyph. A persistent demo header now owns the bell and profile controls on all primary surfaces.
- `web/components/sidebar/ProfileMenu.tsx`: Bug, Lightbulb, MessageCircle, and other existing settings glyphs. SVG paths are copied from the checkout's installed `lucide-react` package, with its license alongside them. Logout keeps the existing muted rose treatment.
- `web/components/sidebar/ProfileDetailsDialog.tsx`: one display-name initial, edit badge, inline display/preferred-name editing, optional preferred name, language access, and a keyboard-accessible seven-color avatar picker.
- `web/lib/avatar-theme.ts`: exact theme order and ambient/picker palette calculations. Localized labels: Default, Sienna, Lichen, Juniper, Lagoon, Iris, Mulberry.
- `web/lib/profile-names.ts`: trimmed values, 60-character display name, 40-character optional preferred name, Unicode code-point counting; Enter saves and Escape cancels.
- Existing `FeedbackDialog.tsx` and English locale: type chooser; bug title (100), reproduction steps (1000), optional expected/actual outcomes (500 each); feature/general details (1000). Required-field gating, counters, type-specific headings, privacy note, Cancel and Submit footer.
- Feature and general feedback intentionally share the production details template; they retain separate type identities and headings.

## Adapted for this phone concept

- Existing profile/menu capabilities are arranged into full-height mobile settings pages. This is not a literal copy of desktop hover submenus.
- Help/legal and feedback stay grouped in the demo; production has separate menu groups.
- The avatar drawer uses the existing mobile four-plus-three swatch layout. Its changes and inline edits do not reanimate the entire settings screen.
- The profile control stays at the same position across Home, Accounts, Chat, Plan, Search and Updates. Branding still follows the previously approved per-surface rules.

## Deliberately left behind / still simulated

- Authentication, profile persistence, API error/loading states and feedback delivery. All names are fictional and all changes reset on reload. The submit outcome explicitly says nothing was sent.
- Feedback tied to an assistant response: thumbs-up/down tags and conversation-context opt-in belong to chat and were not pulled into profile feedback. No screenshot/upload control was added; the existing feedback form does not offer one.
- Actual sessions/passwords, usage counters, memories, archive/restore/deletion, shared links and legal pages remain the earlier illustrative screens. These require separate detailed parity passes; this pass does not claim their full fidelity.
- Desktop-only hover menus, sidebar controls, keyboard-shortcut help and quick-jump badges are not included in this phone study.
- Full Spanish UI and connected language switching remain unimplemented here. Language currently changes the sample preference only, explicitly disclosed in its picker.
- Production feature gates are not changed. Subscriptions remain absent; the preview's financial Updates examples do not activate notifications.
- No image-photo upload was invented for the avatar: the inherited capability is theme selection.

## Verification

Browser checks: identical 44px profile button geometry across five primary tabs plus Updates; seven theme options and arrow-key selection; preferred name can be cleared; display-name length validation and Escape cancellation; bug submission remains disabled until title and steps are entered; feature/general templates show the correct copy; simulated submission reports no send. No horizontal overflow at the tested mobile viewport; feedback footer remains visible. Browser console has no errors. JavaScript syntax checks pass. This is a browser concept, not an iOS/Android implementation.

## Follow-up: settings additions

- Preferred currency uses Lucide Coins. Shared links is now Shared Conversations throughout the preview, including the empty state; future artifact sharing is not implied.
- Root settings ends with the same Argus A mark as chat, subdued and decorative.
- About Argus includes a Star / Rate the App row. The preview explains the future native store destination; no store listing or rating request is fabricated.
- Notifications is a proposed MVEE settings surface, not an inherited live capability: local push/email choices, six topic choices, a daily/weekly/off brief with day/time, and editable overnight quiet hours for financial push alerts. Device permission stays explicitly unrequested. In-app Updates remain available with delivery off. Financial amounts stay out of push/email previews; household content respects sharing boundaries. No scheduling, emails, browser permissions, or notifications are actually performed.
- Removed the demo's unexplained @alex. Current source: ProfileDetailsDialog.profileHandle prefers profile.username, otherwise prefixes the email local part with @. web/app/page.tsx signup sends display_name, email, password and language, not username. The backend can accept an optional username and persists username from auth metadata. An email-derived display handle is not proof of a user-chosen or uniquely reserved username. Production remains untouched.

## Scroll-edge polish

Production chat's masked backdrop blur informed the treatment, but the current preview deliberately uses a stronger 6px blur and a 136px top fade. Solid header backgrounds were removed so the effect flows continuously from the top behind sharp header controls. It applies across app surfaces including chat and settings subpages; the Profile & settings overview and Personal details are excluded. Bottom fades clear at the end of scrolling; chat's bottom fade follows the transcript boundary above the composer. Feedback keeps its existing pinned footer.

Decorative overlays ignore pointer events. Reduced-transparency users get solid headers without the overlays; reduced-motion users get no opacity transition. This supersedes the earlier short, 0.8px list-edge experiment.

Browser verified Search and Notifications mid-scroll and the profile exclusion. Production source is unchanged.

## Compact navigation

Downward scrolling now reduces the bar to a 270px-wide pill (bounded by available width) with 44px-tall touch targets, retaining all five destinations. Selecting any tab navigates immediately, without an expansion-only first tap. Upward scrolling expands the bar. Updates deliberately fades/slides the bar out for reading and restores it on upward scroll; hidden navigation is inert and excluded from accessibility navigation. Profile/settings retain their existing navigation treatment. Reduced-motion preferences continue to disable transitions.

Verified all five compact targets, single-action navigation to Accounts, and Updates hide/restore with accessibility-tree checks. No production changes.

## Conversation header study

- Uses the existing Lucide History (Recents), Link2 (ShareReceiptAction), and vertical ellipsis icons. Active conversations show Recents, a left-aligned one-line title, Share and Chat options; the cold start shows Recents, bell and profile.
- Chats opens a searchable panel with pinned/recent examples. New chat has one entry point beside Recents in the header. Chat options contains local mark-read/pin/rename/delete controls. Titles truncate before the fixed-width actions; the options panel exposes the full title.
- The disposable session now retains separate conversations when starting a new chat. Recents and global Search point to the same local conversation objects, including renamed titles. Reload still resets everything.
- Sharing remains an explicit layout placeholder, without publication or a public URL. Private-chat permissions and other production gates are not simulated as enabled capabilities. Real cross-surface context transport, household permissions, freshness and interpreter behavior remain deferred. The provisional context picker was removed from the composer study.
- Verified scoped search, sample reopen after New chat, menu access, and long-title ellipsis. No production/runtime code changed.

### Phone title refinement

Conversation titles are hidden in the header below a 600px app-container width. Recents, global Search, and Chat options retain the title. Wider containers retain the one-line title beside Recents. Container sizing follows the simulated device rather than the surrounding desktop browser window. This is a preview breakpoint, not a finalized native safe-area contract.

### Chat fade continuity fix

The active chat transcript now extends to the top of its surface, with initial message spacing inside the scroll container. Previously the outer 88px padding clipped scrolling messages below the transparent header, leaving a hard boundary despite the fade. The first message still starts beneath the controls; the title remains hidden on phones.


## Composer capture study

- One composer supports questions and recording, with a plus menu limited to receipt scans, photos, and files. The two-row composer shows dictation and voice-conversation controls; text or attachments replace the waveform with Send while keeping dictation available. Selected attachments appear as removable chips. Existing greeting and market starters remain.
- Voice uses an explicitly authored transcript that can be reviewed before it enters the composer. Receipt/photo/statement buttons use fictional samples. No camera, microphone, file chooser, extraction, provider, or network operation is invoked.
- Prepared receipt, typed-expense, and voice examples lead to a proposed-entry card. Description, amount and category can be edited before confirmation and corrected afterward. Cards and drafts belong to their local conversation; all data resets on reload. Account, currency and date controls, batch statement review, actual persistence, and cross-surface balance updates remain undefined in this study.
- The provisional financial-context picker and @ asset picker have been removed from the sketch. Starter prompts remain question entry points; they do not attach financial records. Production asset/indicator anchoring is unchanged and is not approximated by mock chips.
- Browser verified receipt attachment, Send, proposed amount editing, confirmation, correction, New chat, prior-chat reopening, voice transcript review and proposal, @ selection and chip removal. No browser console errors were reported. JavaScript syntax checks passed. Production files were not changed.

## Header touch spacing

The shared app header uses one 48px touch-size variable, 8px gaps within both icon pairs, and 16px horizontal padding. Icons remain 20px. Removed the chat-specific zero-gap override so active and empty chat inherit the same spacing. Browser measurements verified 48×48 targets and 8px gaps in both states. This is web-preview CSS sizing; native layouts still need platform safe-area insets.

## Two-row composer refinement

The founder's sketch informs the text-first layout, with Plus below left and dictation/voice controls below right. The placeholder is “Type a message”, without an ellipsis. Toolbar targets are 48px with 8px between the right-side controls; visible icons remain 21px. The microphone opens the existing sample dictation flow. The waveform opens an explicit future-voice-conversation explanation, with no microphone or call activated. There is no hold-to-speak promise or gesture in this preview. Dictation appends to an existing draft instead of replacing it. Browser verified empty/filled controls, target geometry, the voice-conversation explanation, and sending a normal sample question.

## Palette reconciliation

`palette.css` is the standalone sketch's color owner, using the existing Argus muted palette and readable text variants from `web/app/globals.css`, `web/lib/artifact-status-tones.ts`, and `web/lib/failure-treatment.ts` on main `a9286b218`. Components now consume those variables instead of provisional green/gray literals. Existing neutral surfaces, glass opacity, and avatar personalization are preserved. Teal remains a small progress/unread/positive accent; warm red identifies form failures and rose identifies destructive controls. The settings-only dark preview retains the production near-black base and neutral white-alpha treatments; this is not a completed app-wide dark theme. No production CSS was changed.

## Empty-chat edge-light study

The empty greeting A gains a slow, neutral highlight travelling from the left, right, then bottom over a 12-second cycle. Its original geometry, position and opacity remain stationary; only an edge overlay moves. The overlay derives its paths from the existing mark and uses the shared white palette token. Reduced-motion preferences disable the waves and hide the overlay. This is new decorative preview behavior, not inherited production behavior or a loading/progress signal. Navigation/settings logos remain static, and the greeting decoration leaves when a conversation starts.

Home net worth, assets, liabilities, and ordinary money-in/money-out amounts remain neutral. No invented period-change metrics or warnings were added.

## Attachment menu simplification

The Plus menu now has exactly three choices: Scan a receipt, Choose a photo, and Upload a file. Removed the mock financial-context and asset selections, their handlers, and the @-triggered suggestion. Typing @ is ordinary text in the sketch. The original production asset/indicator anchoring is not changed or represented as implemented here. Existing starter prompts, voice controls, attachment removal and sample review lifecycle remain.

## Composer-attached attachment tray

Plus now expands an inline tray at the top of the composer, replacing the starter-chip row while open. Three equal columns pair icons with Scan receipt, Choose photo and Upload file labels. Plus becomes Close, and outside taps, Escape or choosing an option dismiss the tray. Hidden controls are inert and excluded from accessibility navigation. There is no backdrop or modal for the tray; the subsequent fictional capture preview still explains that device access is simulated. Draft text and attachments survive tray toggling.

Bottom navigation remains visible on focus alone; it is hidden and made inert only when the preview detects a reduced visual viewport consistent with a virtual keyboard on a touch device. The tray expands in normal layout, above the input and below the conversation. Reduced-motion preferences remove the expansion transition. Browser checks confirmed starter restoration on outside dismissal, sample receipt attachment/review, non-overlapping active-chat layout, Escape focus return, and roughly 102×72px option targets at the current phone preview width.

## Composer interaction ownership

Typing and the attachment tray are mutually exclusive: focusing the message closes the tray; opening Plus blurs the message. Drafts remain attached to their conversation when switching surfaces. Toolbar pointer presses preserve focus until their click action runs, avoiding a premature layout shift. Background dismissal happens on pointer release after a short tap; starting a scroll does not dismiss the tray. Interactive controls keep their own action rather than consuming a tap to dismiss first. Escape closes the tray and restores Plus focus, or leaves typing; open dialogs retain their own Escape handling.

Navigation visibility now has one setter shared by scrolling and composer keyboard state. Focus alone no longer hides navigation. Scroll-driven compaction pauses while editing or while the tray is open, so content-height changes cannot compete with those interactions. Leaving Chat clears its editing/keyboard state.

Verified in the local browser: typing closes the tray, draft survives Home → Chat, outside greeting tap dismisses the tray without losing text, Escape restores Plus focus, one sample send creates one user turn, transcript scrolling retains the open tray, and a capture dialog closes back to Plus. No console warnings/errors were reported. A 390px viewport was inspected and the override reset. Several toolbar pointer activations were unreliable through browser automation; those controls were verified with keyboard activation instead. Real touch-device keyboard appearance/dismissal, one-tap toolbar targeting during keyboard transitions, and native back gestures remain device acceptance work. This preview uses a viewport heuristic, not a native keyboard integration.

## Founder-locked mobile chat behavior · 2026-09-27

This is the intended mobile experience, not a claim of verified native keyboard support:

- Reading: keep the menu bar available; downward conversation scrolling shrinks it while upward scrolling expands it. A short conversation with no scroll range cannot demonstrate this behavior.
- Typing: when the software keyboard opens, hide the menu bar and place the composer directly above the keyboard. Desktop text focus without a software keyboard leaves navigation available.
- Keyboard dismissal: return the composer to its resting position and restore the menu bar, preserving the draft.
- Plus while typing: close the keyboard and open the attachment tray above the composer; restore the menu bar. Keyboard and tray are mutually exclusive. Coordinate the transition so the composer does not jump through an intermediate layout.
- Outside background tap: dismiss the keyboard or tray without sending or clearing anything. Interactive controls still perform their own action on the first tap.
- Conversation scrolling: scroll normally; starting a scroll alone must not dismiss the keyboard or tray.

Validate keyboard geometry, safe areas and transitions on real iOS/Android devices when implementing native clients. The desktop sketch cannot establish that acceptance.

## CTA hierarchy and typography · 2026-09-27

The shared `surface-controls.css` owns the sketch's surface CTA styling: near-black primary pills, light neutral secondary pills, white primary labels, 48px minimum height, and Space Grotesk medium labels at 16px. Updates now uses primary surface actions instead of chat follow-up styling. Decorative forward/external arrows were removed from surface CTA copy; navigational choice/Search rows use a consistent trailing chevron. Back controls retain directional meaning. Chat's conversational follow-up contract is unchanged.

The sketch now serves byte-identical Inter and Space Grotesk variable font assets from the checkout's `web/app/fonts`, with their licenses and attribution, instead of requesting Google Fonts. Shared surface headings use Space Grotesk 500 (32/22/18px), body copy uses Inter, and financial figures use Space Grotesk with tabular numerals. Settings and chat retain their more specific inherited sizing. These mobile sizes adapt the design hierarchy; the marketing-scale examples in DESIGN.md are not phone defaults.

Browser checks covered Updates button colors, 48px targets and Plan navigation, Accounts primary/secondary controls, Search chevrons, Home figures, and the inherited settings view. No production files were changed in this pass.
