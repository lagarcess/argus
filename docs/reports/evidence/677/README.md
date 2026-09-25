# Issue 677 evidence

Playwright captured these mocked 503 guest-claim error states at the
exact PR head. The API body still says
`Argus could not start this turn. Please try again.`; the client maps
`guest_compute_claim_unavailable` instead of rendering that English
detail.

| Locale | Error state |
| --- | --- |
| en | [en-claim-503.png](./en-claim-503.png) |
| es-419 | [es-419-claim-503.png](./es-419-claim-503.png) |
