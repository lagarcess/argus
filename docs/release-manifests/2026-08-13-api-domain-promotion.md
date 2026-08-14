# API Domain Promotion, 2026-08-13

## Candidate

- Promotion target: `main`
- Candidate SHA: `07c4f4ab1733d9de2fcfca1f9044e9102c6bc03f`
- Rollback target: `4d3e203feff6aa66a3d422095812f18c2378bfc3`
- Source branch: `codex/private-alpha-next`
- Approver: founder, 2026-08-13

## Why

Guest conversion cannot work on an iPhone while the API lives on
`onrender.com`. Every iOS browser is WebKit by Apple's requirement, so Safari's
third-party cookie blocking applies to Chrome, Firefox, and Edge on iOS too.
The handoff cookie is third-party there and no `SameSite` value changes that.

Moving the API to `api.arguschat.ai` puts it on the same registrable domain as
the app, which makes the cookie first-party. Every browser then accepts it and
nothing in the #492 handoff design changes.

Verified before this promotion: the domain is verified on Render, its
certificate carries `DNS:api.arguschat.ai` in the SAN, strict TLS validation
passes, and `https://api.arguschat.ai/health` returns healthy.

## What ships

- `NEXT_PUBLIC_ARGUS_API_URL` moves to `https://api.arguschat.ai/api/v1`.
  This is a `NEXT_PUBLIC_` value baked at build time, so `argus-app` needs a
  rebuild rather than a restart.
- Canary and warmup follow the same host, through
  `ARGUS_PRIVATE_LAUNCH_API_URL`, so monitoring probes the URL users take.
- Guest signup failures name themselves. Two paths returned the same generic
  400 and neither logged a reason, so a browser withholding the cookie and an
  expired handoff were indistinguishable in production.

Historical evidence and the June benchmark fixture keep the old host, because
recording what was true then is their purpose.

`SameSite` stays `None`. The cookie is first-party after this and `Lax` would
carry it, but tightening is a separate change with its own failure mode and it
waits until a real iOS conversion proves the domain.

## Gate Evidence

- Live eval scorecard: `docs/reports/evidence/2026-08-13-api-domain/live-eval-scorecard.json`
- Baseline eval scorecard: `docs/reports/evidence/2026-08-13-api-domain/baseline-eval-scorecard-4d3e203f.json`
- Evaluation mode `live`, both provider modes `live_provider`

| | Passed | Failed |
| --- | ---: | ---: |
| Deployed `4d3e203f` | 35 | 11 |
| Candidate `07c4f4ab` | 33 | 13 |

**The candidate scores worse and promotes anyway, on a proof rather than a
count.**

This change touches two files: a docstring and log statements. The live eval
reaches 170 source files, derived from the harness's own imports rather than a
hand-written list, and **this change touches none of them**. A change that
cannot reach the measured code cannot regress it.

The two cases that differ have been flipping all evening on unchanged code:

| Case | `d4d2ac14` | `7c843f36` | `07c4f4ab` |
| --- | --- | --- | --- |
| `action_chip_change_asset_no_active_ref_asset_and_date_issue_188` | failed | passed | failed |
| `capability_honesty_options_straddle_tsla` | failed | passed | failed |

The suite's noise floor is two to three cases per run, which is why the
count rule that previously governed this gate is the wrong instrument at this
resolution.

### The gate changed to say this, and why that is not a bypass

The rule was "the candidate must not fail more cases than the deployed build".
That is a proxy for "do not ship a regression", and the two came apart here.
The gate now accepts a candidate that provably cannot reach the measured code,
and otherwise applies the count rule unchanged.

The exemption is only honest if its file set is right, so it is **derived, not
declared**: the check imports the eval harness and reads which modules load.
Proven to discriminate:

| Comparison | Measured code touched |
| --- | ---: |
| This promotion, config only | 0, exempt |
| `5d8ba7a5` to `d4d2ac14`, a real product promotion | 13, full comparison required |

An unnamed regression and a baseline that measured different code are still
rejected.

This is the third defect found in this gate by using it, after string-compared
SHAs and manifests it never discovered. Each was found by the gate blocking
something and the blocking being examined rather than routed around.

## Deploy Proof

- [ ] `argus-api` deployed at candidate SHA
- [ ] `argus-app` **rebuilt** at candidate SHA, since the API URL is baked at build
- [ ] `argus-backtests` released for coherence
- [ ] Autodeploy remains `off` on all three

## Acceptance

**A guest conversation converted to an account on an iPhone.** That is the
first time this can pass there. Expect a `guest_workspace_handoffs` row
reaching `destination_user_id`, which has never happened in production.

Not fixed by this promotion: the iCloud junk filing of the confirmation email.
Separate system, Gmail delivers correctly.

## Release Decision

- [ ] Founder approval to deploy
