# Issue #480 guest signup handoff evidence

Captured on 2026-08-12 against a disposable local Supabase Auth stack with the
repository's dashboard template snapshot loaded into Mailpit.

The English and Spanish browser journeys each:

1. created a real anonymous guest;
2. produced an Argus confirmation card and completed a synthetic-provider
   backtest;
3. registered through ordinary Supabase signup;
4. confirmed the signup email and signed in;
5. verified the permanent Auth UUID differed from the guest UUID;
6. verified the conversation, messages, job, run, and evidence artifact moved
   to the permanent account and restored after reload; and
7. verified Auth audit actions included `user_confirmation_requested` and
   `user_signedup`, with no `user_modified` action.

The matching local integration tests inspect the rendered Mailpit message. They
assert the signup subject and address in both languages, and separately prove a
genuine email change renders the old and new addresses through the unchanged
email-change template.

Screenshots mask visible email and password inputs. They show the guest result,
the signup-confirmation state, and the same result after confirmation, sign-in,
handoff claim, and reload for both supported languages.

Run the focused browser proof with:

```bash
bunx playwright test --config e2e/issue-480-guest-signup-email.playwright.config.ts
```

This requires the disposable local Auth stack, Mailpit, synthetic market data,
and the loopback endpoint variables used by the guest QA harness. It does not
apply the migration to a hosted environment or send external email.
