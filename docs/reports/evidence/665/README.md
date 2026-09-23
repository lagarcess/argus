# #665 guest `captcha_unavailable` UX fixtures

Static HTML fixtures of the empty-chat guest error and AuthForm failure path
(EN). They use the same locale strings and actions as
`EmptyChatSurface` and `AuthForm`. This is **not** a live Turnstile session:
the cloud environment cannot complete a real Cloudflare check, and production
Turnstile is not bypassed.

- `before.png` — parent-tip behavior: generic temporary-chat copy + **Try again**;
  AuthForm still said “try again.”
- `after.png` — this tip: `auth.errors.captcha_unavailable` + **Reload**
  only on empty chat (Sign in is a same-browser dead path); AuthForm uses
  the same honest copy and keeps submit.
- `before-after-collage.png` — both columns together.

Source HTML (gitignored): `temp/issue-665-ux-fixtures.html`.
