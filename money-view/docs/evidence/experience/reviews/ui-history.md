# Independent UI lifecycle review

## Latest delta rereview: ui-fixes-final

Verdict: **proposal-confirmation and route-pagination findings closed; one residual P2 in delivery acknowledgement**. Compared only the changed proposal state, acknowledgement and route reset against the original UI package. All 27 current files in `ui-fixes-final/manifest.json` matched the frozen manifest before verification. Manifest SHA-256: `157c3050573e15eaf38dd1ef343de11d07a10c9ff63e627ea06906340bb68c1f`.

Exact changed identities:

- `cards.tsx`: `bcc9e142cb4f9f95885ccadc5259c1cf8c3d0bfd6c9db7d88830e27e6f26ffb8`.
- `ConversationPage.tsx`: `676523a71989dfd28a5db8e6c7b7ee9f6b185192a49da6a10c3d6fe4ac41073d`.
- `drafts.ts`: `bc6694930daa62fd4c6e92f1a2bf0f4b6f5384c6b518884f626c4addb925d1a5`.
- `proposal-state.ts`: `33b2c2dfc15f2359fe9bc48197639084cf5c435ebe3218b25cdccdfbf588b3cd`.
- `drafts.test.mjs`: `a0265938c1ebc8a142d3e944247bf88db70737f133930fe92674b8629a654f6a`.
- `proposal-state.test.mjs`: `c17e0ab649cfaceea179b23c825d2ab9850028e619931adc21fddfcae46baf0e`.
- `ArgusComposer.tsx` remains unchanged at `3fbdc7f204087ab74eb32f2d8915415f7f00b42de92e144bd0bf24e09b3e8611`.

**Closed findings:** Confirm is absent while editing, failed saves remain editing, and accepted saves wait for canonical proposal revision hydration before confirmation controls return. Route reset now clears `loadingOlder` while the prior request's obsolete completion remains suppressed.

### P2: Acknowledgement compares a different text representation from Send

Locations: fixed `ConversationPage.tsx:184-188` and its composer dock `onInputCapture`; `drafts.ts:71-74`. The comparison is newly introduced by this fix.

`composerTextRef` and sessionStorage are populated from `editor.textContent`. Send still obtains text from `serializeComposerSegments(readSegmentsFromEditor(editor))`. These are not the same representation: serialization normalizes whitespace, includes line breaks represented by DOM BR/block nodes, and uses a mention's `insert_text` (such as `@Checking`) instead of its visible label (`Checking`). Programmatic mention insertion also updates the composer without a native input event reaching the parent's capture handler.

The new exact-text equality therefore misidentifies unchanged drafts as newer edits. A successful inline Retry still leaves those drafts visible. A normal successful send clears the composer's own state but can leave the unmatched storage entry behind, resurrecting accepted text after reload. This is the same delivery-owner bug class, not a request to broaden behavior.

**Reproduced with the frozen serializer and acknowledgement helper, without network:**

```text
tracked:   "ask about spending  "
delivered: "ask about spending"
after:     "ask about spending  "

tracked:   "first linesecond line"
delivered: "first line\nsecond line"
after:     "first linesecond line"

tracked:   "Review Checking"
delivered: "Review @Checking"
after:     "Review Checking"
```

The first case needs only ordinary trailing spaces. The latter two follow the inspected DOM reader and token-label writer. No user edit between failure and retry is required.

**Small correction:** let the composer own the draft snapshot used by both delivery and acknowledgement, including changes made by mention insertion and deletion. Expose that canonical snapshot/edit identity to persistence instead of reconstructing it through parent `textContent`. Acknowledge only the submitted snapshot so genuinely newer edits still survive. Adding `.trim()` to one comparison would leave multiline/mention cases split.

**Needed regression:** first failure then successful retry for plain text with trailing whitespace, Shift+Enter/multiline text, and an inserted account mention; accepted draft and its storage must clear. Repeat successful ordinary send plus reload to check storage. Preserve a genuinely newer edited draft during retry and keep typed-action completion from clearing it. Existing tests pass only identical plain strings into the helper and do not exercise the composer boundary.

Browser owner remains responsible for the interaction regressions; no browser, network, or model execution was performed in this rereview. Only this report changed.

## Original review record

Verdict: **three actionable P2 findings in the frozen UI lifecycle package**. Import review remains clean and was not reopened. Findings are traced through rendered conditions, callbacks and React ownership; this review made no browser/network/model calls and does not claim a fresh browser reproduction.

## Reviewed identity

Package: `temp/argus-experience/review-packages/ui-lifecycle/`. Its `manifest.json` records all 32 exact file hashes (manifest SHA-256 `34bf9f8b3b28b4527a310202087a3fd95961265e1d3e02104a2b90eb1ec13499`). All 32 working files matched that manifest at the review's initial comparison; no superseded currency-hint or human-label finding is reported. The snapshot already contains `default_currency` transport hints separate from explicit typed-action currency.

Affected files:

- `money-view/web/src/features/chat/cards.tsx`: `4c1a9a4ad3992d66b7ec53080ac4f4d6a74ec0ceb18437d7aa9b296e7ec89a82`.
- `money-view/web/src/features/chat/ConversationPage.tsx`: `8d405811a4dddc7e9717d8714bc13768b0fe8306dc57bbbf50a501be86c0f80e`.
- `money-view/web/src/argus/ArgusComposer.tsx`: `3fbdc7f204087ab74eb32f2d8915415f7f00b42de92e144bd0bf24e09b3e8611`.

Relevant ownership boundaries also reviewed:

- PlatformApp: `d37b42d50ef48458ec2b35613390471a3b3974857f9224799fbeb55e14f37869`.
- Shared resources: `5c596f836c5c740d2e34f5d6eb7560a45e294864cad32eb303b496badca1fa37`.
- Draft storage: `1ff546af05c252f7a7819ff5b846130a3c3cfd5bf778bf9f0d25407ad5ed98c4`.
- Native modal: `4a222d553a21bd22c6829e29f94560e3d5ab3d164769ff0dd95c704a21a07c08`.
- Modal Back hook: `c6ed120bb19735f266a9ae1a5e54fb268ca67f05c05b4e7cbfd75f6a1e2c977e`.
- Overlay history: `69b1709a66df3eef19cd45ec2c7346479442074857edd30baf830f33ea39fbbb`.
- Navigation: `12be03ffc2ce372e84b889c1021691083f8213ca06bb3d37c7753429c3a730eb`.

## P2: Confirm can commit the old proposal while unsaved edits are visible

Location: `cards.tsx:292-298`; confirmation transport at `ConversationPage.tsx` inside `mutateProposal`.

`ProposalCard` keeps its active Confirm action rendered while `editing` is true. Its disabled condition checks only `busy` and missing required fields. Clicking it calls `onConfirm(proposal)` with the persisted proposal; local `drafts` are only sent through the separate Save edits form.

Reachable sequence: open a pending proposal for amount 400, click Edit, change its visible amount to 500, then click the still-enabled Confirm. No PATCH occurs. Confirmation sends the old revision and can persist amount 400 while the user is looking at 500. This breaks the connection between the displayed review and the authorized write.

Small correction: make editing and confirmable review mutually exclusive. Save edits must finish and display the server-returned proposal revision before confirmation is enabled. A failed save must not leave a Confirm button attached to stale hidden values.

Required test: edit a monetary value, attempt Confirm before saving and assert no confirmation request; save, inspect the revised value/revision, then confirm exactly once. Cover a failed/conflicting save and canceling an edit. Use mocked transport or the existing deterministic local fixture; no model call is needed.

## P2: Successful inline retry leaves the already-sent text in the composer

Locations: `ConversationPage.tsx:177-187`, `:371-372`, and `ArgusComposer.tsx:146-161`.

Normal successful submission clears the composer through `ArgusComposer.submit` after `onSend` returns acceptance. A failed submission returns false and correctly retains the text. However, the inline Retry button calls `completeTurn(retryPayload, false)` directly. Its successful branch removes sessionStorage and clears retry state without telling the still-mounted composer that its text was accepted. In an existing conversation the composer key does not change, so its DOM still holds the sent text and Send remains available.

Reachable sequence: in an existing conversation, submit text, receive a transient failure, then click the inline Retry and receive a completed response. The transcript refreshes, but the original text remains in the composer. Pressing Send again generates a fresh turn ID and submits it again. Clearing storage alone cannot clear this second owner of the draft.

Small correction: give accepted delivery one shared draft/composer acknowledgement path used by original submission and retry. Clear only the draft that was accepted; preserve any different text the user typed after the failure.

Required test: mock first failure then same-turn successful retry in an existing conversation; assert the original ID is replayed, the composer empties and Send disables. Also edit the draft after failure, retry the older payload and verify the newer text survives.

## P2: Changing conversations during older-history loading leaves pagination disabled

Locations: `ConversationPage.tsx:112-135`, `:321-335`, `:362`.

`loadOlder` sets `loadingOlder=true`. Navigating from conversation A to B changes `routeScope`, aborts the old request and increments the epoch. The old request's `finally` intentionally avoids state updates after that change, but the route reset never resets `loadingOlder`. PlatformApp keeps the chat page mounted for conversation-to-conversation navigation (`key` is workspace plus page), so B inherits true and its Older messages button remains disabled.

Reachable sequence: two conversations each exceed the first 50-message window; delay A's older-page response, switch to B, then inspect B's older-history control. It remains loading/disabled even after B's initial page loads, until the component fully remounts.

Small correction: include pagination request state in the route-owned lifecycle reset, or keep it keyed by the same scope as its data. Do not let the aborted old request clear state in the new route.

Required test: delayed A history request, switch to B, settle/abort A, then load B's older page successfully. Assert A's messages never enter B.

## Verified boundaries and limits

- Draft keys include user, household and data generation; staged routes contain an opaque draft ID rather than user text. Workspace/page component keys and resource dependency checks prevent the previous workspace's loaded data from rendering as current.
- Conversation route epochs and abort checks protect turn, proposal, owner, export and history response application. The pagination busy-state omission above is the concrete exception found.
- Composer retains rejected sends, preserves typed mention provenance, rejects rich file pastes, and uses the statement owner's explicit attachment entry.
- Native dialog owns focus trapping/Escape; the shared overlay registry owns Back and navigation consumption. No additional concrete focus/history defect was established in this scope.
- Fresh local verification: composer-model, overlay-history, draft and transport Node suites **16 passed, 0 failed**. These are source/unit checks, not the three missing interaction regressions. Root's separate browser and visual evidence remains separate evidence.

Only this report was edited. No product, Git, production, environment, Supabase, network, deployment or live-model changes were made. Review frozen pending bounded fixes to these findings.
