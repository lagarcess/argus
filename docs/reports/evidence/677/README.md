# Issue 677 evidence

Playwright captured the mocked 503 guest-claim error on
`9fa00690` (before) and this PR head (after). The API body still says
`Argus could not start this turn. Please try again.`; the client on this
branch maps `guest_compute_claim_unavailable` instead of rendering that
English detail.

| Locale | Before (`9fa00690`) | After |
| --- | --- | --- |
| en | [before-en-claim-503.png](./before-en-claim-503.png) | [en-claim-503.png](./en-claim-503.png) |
| es-419 | [before-es-419-claim-503.png](./before-es-419-claim-503.png) | [es-419-claim-503.png](./es-419-claim-503.png) |

A second claim 503 on Retry used to reload `GET .../messages` (empty, because
the claim runs before the user turn is saved) and wipe the local transcript.
`en-claim-503-retry-again.png` is the after of that path: the composed
message, localized notice, and Retry countdown stay on the second 503.
