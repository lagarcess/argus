# Frontend integration review

Scope: read-only review of the shared shell/client/hooks/UI, deposit integration, settings consumer boundaries, and the existing browser test source. No implementation edits, Git operations, network calls, or browser-matrix reruns. Existing browser tests were inspected as coverage evidence, not represented as freshly executed verification.

Result: four confirmed P2 findings; no P1 identified in this bounded review.

## P2: Newly created household members have no usable login path

Owner: `money-view/web/src/platform/PlatformApp.tsx:573-594,675-687`, together with the successful member-creation result in `money-view/web/src/features/settings/household.tsx:28`.

The login form can submit only IDs from `/demo/personas`; its only identity input is a select whose options are that response. The API contract intentionally limits this catalog to fixture users (`server/platform/identity.py`, personas query `WHERE fixture=1`). `POST /household/members` creates an ordinary local user, whose fixture flag is false. The member form then discards the returned login ID and closes. There is no typed local-user ID login field or equivalent handoff.

Reproduction: as the owner, add a demo member with a valid local password, confirm the member appears in Household, sign out, then attempt to sign in as that member. The member is absent from the only identity selector; the created credentials cannot be used through the UI. This affects every UI-created member, not just an unusual role.

Smallest safe fix: make local-member creation expose its returned login identity and give the login flow an explicit path for that identity, while retaining the fixture picker. Alternatively define a deliberate local-demo login catalog policy; do not accidentally broaden fixture-public profile exposure as a side effect. Keep the login ID owned by the successful create response.

Acceptance: create member through Household, sign out, log in through the actual UI using that member's password, and verify the requested role and household. Existing `platform.spec.ts` exercises seeded owner/viewer/other-household personas, not a newly created member's login.

## P2: Binary download paths leave private views mounted after an authentication failure

Owner: shared response/error handling in `money-view/web/src/platform/client.ts:36-41`; bypassing consumers are `features/ledger/TransactionsPage.tsx:79-92` and `features/assistant/AssistantDrawer.tsx:51`.

JSON requests dispatch `clara:session-expired` for `401 authentication_required`, which the shell uses to remove the authenticated workspace. Both download functions instead call `fetch` directly. Transaction CSV export throws a generic error on any non-OK response; assistant export constructs an APIError locally. Neither sends the session-expired event, and neither success refresh callback runs after the failure.

Reproduction: load transactions or a saved assistant conversation, revoke this browser's session from another session (or let it expire), then make the next action Export CSV / Export conversation. The server refuses the request with 401, but the old private rows/conversation and authenticated shell remain visible with only a generic export error. They remain until another request happens to pass through the shared JSON client.

Smallest safe fix: give binary downloads the same canonical response-status handling as JSON requests, through a shared download/response helper. Avoid separate auth-status checks in each feature.

Acceptance: for both export paths, a mocked or locally revoked `401 authentication_required` must clear the authenticated shell and show login; ordinary 413 export failures must retain the session and show the size error. Existing browser tests cover deliberate sign-out and successful exports separately, so they do not establish this boundary.

## P2: Deposit notice navigation is dropped while another deposit action is pending

Owner: selected-resource loading at `money-view/web/src/features/deposits/DepositsPage.tsx:30-34`, with the shared pending guard in `money-view/web/src/useMoneyView.ts:202-217`.

The selected-decision effect calls `openDecision`, but `openDecision` returns immediately for any pending deposit action. The effect depends only on selected ID, notice ID, and home data. When a compute/interpret operation finishes, it changes conversation/pending state without refreshing home; none of those three dependencies changes, so the requested decision is never fetched. Header notice navigation remains available during the deposit operation and changes only the query, keeping the same deposits component mounted.

Reproduction: start a deposit calculation while home sources are ready and delay its response. Before it finishes, open the header notice center and select an existing saved-deposit notice. The URL now requests that decision/notice, but the effect is skipped because pending is `compute`. Release the calculation response. The screen remains the generic saved list (or the previously loaded decision for a same-decision notice), with no fetch for the requested before/after artifact until navigation/reload changes a dependency.

Smallest safe fix: let the selected decision/notice have an independently keyed read lifecycle that cannot be discarded by the mutation lock, or explicitly retry the selected intent when the blocking state clears and suppress obsolete responses. Do not change the canonical before/after payload selection in SavedDetail, which correctly uses the notice's immutable snapshots when present.

Acceptance: delay compute or interpretation, navigate to a saved notice, finish the earlier request, and verify the requested notice's exact before/after IDs render without reload. Existing `pilot.spec.ts:24-57` waits for compute/save/load completion before opening notices; it covers the sequential path only.

## P2: Household add/rename failures are hidden inside their modal

Owner: `money-view/web/src/features/settings/household.tsx:27-28`.

The add/rename modal is rendered only when `editor` is truthy, but its ActionState is itself gated by `!editor && !removing`, so it can never render. The outside ActionState has the same gate and also disappears while that modal is open. The mutation helper correctly records the failure, but both consumers hide it.

Reproduction: open Add demo member or Edit household name, enter a whitespace-only name (native required accepts spaces), and submit. The handler trims it to empty, the backend correctly returns 422, and the modal stays open with no error or explanation. The same dead error surface also hides connection failures and permission changes.

Smallest safe fix: render the mutation's ActionState unconditionally within the active editor modal, keeping background status hidden if desired. This is a consumer rendering correction, not a change to backend validation.

Acceptance: reject the add and rename requests and verify a visible role=alert inside the still-open dialog, with entered values retained and retry enabled.

## Inspected without an additional finding

- `ActivePage`, NoticeCenter and AssistantDrawer are keyed by user and household; `useResource` clears dependency-mismatched data immediately and guards obsolete fulfilled/rejected callbacks.
- Shared JSON 401 handling and the shell's expired state remove the authenticated workspace. The finding above is limited to the direct binary-fetch exceptions.
- Currency selection derives from household policy / supported server catalog. The overview selects a matching currency slice and labels no conversion; account amounts render their own stored currency.
- EvidenceLine visibly distinguishes publication date from observation date and exposes recording details. Deposit SavedDetail uses notice.before/notice.after when the correct notice has been loaded.
- The native shared dialog provides modal keyboard ownership, a named heading, Escape handling and focus restoration. Destructive member removal and data reset show explicit consequences and require confirmation; this review did not replace the separate browser accessibility matrix.

## Reviewed source fingerprints

These hashes identify the inspected files for delta-only follow-up; they are local review evidence, not browser acceptance evidence.

- `money-view/web/src/platform/client.ts`: `e7d44d8a6c489b628a56786a7554252cd2c0f66adc99190b7b0998c4bc50a4d8`
- `money-view/web/src/platform/hooks.ts`: `5c596f836c5c740d2e34f5d6eb7560a45e294864cad32eb303b496badca1fa37`
- `money-view/web/src/platform/PlatformApp.tsx`: `2184cefc2d66a770fe9d7efd01ab11672095b45f0eefd9db28fa07ee24711669`
- `money-view/web/src/platform/ui.tsx`: `bbbd4b457916f709a655ecb5376c33fb0781c27660f8cec5ce393e53088f5595`
- `money-view/web/src/features/deposits/DepositsPage.tsx`: `005f1dbbb7bee700357652c062f6d2e9957cb8de131e845bd2e46625fd7f06eb`
- `money-view/web/src/useMoneyView.ts`: `42bc7a7b727cacee9ca74261a45c42d280c5a83f5f733f95bfc22f042cb2d8ae`
- `money-view/web/src/features/settings/household.tsx`: `972eb28db749704043dceb7f84832d85959e8caefcc132226332daedf24d2325`
- `money-view/web/src/features/ledger/TransactionsPage.tsx`: `1a563a366bd9d8401deb965f7ca48fdcd4c48a3bcd60d0e5d3bc45a243887683`
- `money-view/web/src/features/assistant/AssistantDrawer.tsx`: `cc6d17a6549bbc0cab37d233ad95d1dcf3e495d3a2f6b5405a44764cd3d4b68e`

## Final scoped re-review of the four fixes

Outcome: **CLEAN for the four reviewed P2 fix deltas. No remaining P1/P2 finding in this scope.** This pass did not reopen unchanged feature code or expand the acceptance requirements.

1. **Local-member login closed.** The login form now separates fixture selection from explicit local-account ID/password entry. Local credentials are independent of the fixture catalog request and remain intact when switching login modes. Household creation validates and retains the successful `user_id` response, displays a selectable/copyable receipt with login instructions, clears the password after success, and exposes the persisted member ID to the owner after the receipt is gone. No public fixture catalog expansion was introduced.
2. **Binary-export authentication closed.** `requestResponse` is the only remaining fetch owner under `web/src`. JSON requests, legacy deposit requests, CSV downloads and assistant JSON downloads all pass through its shared authentication-required event before parsing bodies. The binary callers preserve their download behavior and the assistant retains its explicit oversized-export error handling. Only `401 authentication_required` expires the session; ordinary export-limit errors do not.
3. **Dropped deposit target closed.** Selected decision/notice loading now waits while pending and reruns when pending clears. The attempted-target ref is set before calling openDecision, so its own pending transition cannot loop, and a failed/invalid target is attempted once rather than continuously retried. A different notice on the same decision produces a different target; leaving selected mode clears the ref so deliberate navigation back can retry. Existing SavedDetail continues to render the selected notice's before/after records.
4. **Hidden household-editor failures closed.** The add/rename form now renders ActionState inside its active modal without the impossible `!editor` guard. Mutation failure leaves the dialog and entered values in place; success alone closes it. Background status remains separately gated.

Evidence inspected: the new `e2e/frontend-review.spec.ts` covers editor/viewer creation through the receipt and actual local-ID login, wrong-password preservation, both whitespace-name error dialogs, CSV export after real revocation in a second client, notice selection behind a gated compute request, and one-attempt invalid target recovery. `e2e/assistant-export.spec.ts` covers authentication-required during export after answers are visibly loaded. This re-review inspected those test definitions and did not run or claim the browser matrix. The captain reported the existing 19 browser journeys, assistant-export regression, build/Ruff and 363 backend checks green; the new focused browser run was still assigned to the browser worker when this review was requested.

Final reviewed file fingerprints:

- `money-view/web/src/platform/client.ts`: `c29262f41d97b81fb411bdb9fe62b3b01ce52b6ec989d7d277a11e7e1795ddd7`
- `money-view/web/src/api.ts`: `d87ff7bfab0045de4e9c55a4244831b004456355153b77bea77f31ce635ad4f6`
- `money-view/web/src/platform/PlatformApp.tsx`: `da78bab737f7c4b632a3943b2753d673467b49cc905b9ef7ef1ca00503f1b135`
- `money-view/web/src/features/settings/household.tsx`: `b5a024cf2328705fb07c1fd5334f186fb95713de72703012e79e6b8bb2135609`
- `money-view/web/src/features/deposits/DepositsPage.tsx`: `80ce6d6c1ef749ea5569c549baeb0e913587a7559dc932d7fd6cebf7edf7ddda`
- `money-view/web/src/features/ledger/TransactionsPage.tsx`: `0f86e7733605ce0e8bb5c707866b79a7ea837d822cf087e709106eed00f7ec14`
- `money-view/web/src/features/assistant/AssistantDrawer.tsx`: `4322eb0bc38d81d106c8001d9f92121ffeb2a5f0f807ec33312bc5d28545ef83`
