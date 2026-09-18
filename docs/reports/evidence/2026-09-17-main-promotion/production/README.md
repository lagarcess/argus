# Production promotion, 2026-09-17 America/Chicago

The release is deployed at `a9286b21886eb03df7a21f2f4b7d5e79af570679`, which contains the approved `cfc1988d` integration cut and sharing configuration. PR #655 merged at 01:51:17 UTC on September 18. Both candidate CI runs and landed main CI passed.

The founder explicitly waived the database backup and hosted staging services, and accepted the local shared-link follow-up misread. No backup was taken. Both canary suites stayed skipped; the retired workflow remains disabled and #614 closed as not fixed.

## Schema

`production-before.json` found exactly four pending migrations. `production-apply.json` records their atomic application at 01:41:15 UTC, preserving canonical versions and statement arrays. `production-after.json` and `production-landed.json` pass with zero pending migrations and no new name/content drift. The latter verified landed `origin/main` before any deployment.

Production has 81 ledger rows against 79 repository files because of the checked-in historical reconciliation, which still matches. `production-objects-after.json` confirms widened excerpt/tier checks and service-role-only SECURITY DEFINER claim/release functions.

## Services

| Service | Commit proof | Deployment/version | Result |
| --- | --- | --- | --- |
| argus-api | `a9286b21886eb03df7a21f2f4b7d5e79af570679` | `dep-dam9irgu01pc73erp4i0` | live |
| argus-app | `a9286b21886eb03df7a21f2f4b7d5e79af570679` | `dep-dam9iumk1f9s73eoe450` | live |
| argus-backtests | same full SHA explicitly requested; ready version reports `a9286b2` | `wfv-dam9k6942hec738qgjf0` | ready |

API and app deployments were started, in that order, by the Render MCP sharing environment updates. Their builds overlapped. Backtests was released after both were live using the repository's Render CLI/API command because MCP exposes no Workflow operation. Runtime warmup and the release-profile audit passed; Workflow effective provider mode is `live_provider`. Both sharing flags are true and all deploy triggers remain manual.

The first MCP writes were rejected without mutation because no workspace was selected. Supplying the verified `argus-prod` workspace fixed this. A redundant API deploy was queued by a separate trigger and cancelled. The CLI initially used an expired saved login; the existing valid MCP credential completed cancellation. None of the three active release deployments failed.

## Production walk

1. A temporary registered QA user asked: “I have $1,200 saved. If I save another $300 each month with no interest, how many months until I reach $3,000?” The answer and card correctly showed **six months**. The answer also exposed the raw line **`months_to_goal: 6`**, a display defect retained in the shared page.
2. Selected the question/answer, previewed it, and clicked “Make the link.” Publication succeeded.
3. A separate browser started with zero cookies/storage origins; after opening the public link it still had zero cookies and no auth-token storage. It displayed the question, answer and calculation inputs signed out.
4. From the public page, submitted “What if I save $450 per month instead?” Real production CAPTCHA/guest creation succeeded unchanged. A distinct guest chat displayed the shared snapshot, then replied: “Got it, $450 per month. To run that test, which asset or assets would you like to invest in, and over what date range?” This reproduces the founder-accepted misread; expected arithmetic was four months. No model question was retried.
5. The same public page with `Accept-Language: es-419,es;q=0.9` localized chrome, labels, disclaimer and composer. The immutable authored question/answer stayed English.
6. Revoked the test receipt with its owner's normal API. Anonymous readback returned the documented HTTP 200 tombstone (`status=revoked`, `payload=null`), and the Spanish page displayed “Este ya no está.” Both temporary sessions were globally revoked, both accounts deleted, and absence confirmed. No existing user was changed.

Screenshots and text/console/request evidence are in `sharing-walk/`. Owner console: zero errors/five font preload warnings. Public English before follow-up: zero errors/one font warning. Final reader: five errors/six warnings, including three pre-auth API 401s and two Cloudflare challenge console errors; guest/fork/stream still succeeded. Spanish public page: zero errors/one font warning. No uncaught application exception was observed. Third-party challenge path identifiers are redacted.

Two production user questions generated 13 priced cost-ledger entries totaling **$0.04631143 reported**. Compute/build costs are outside this LLM total. `production-walk-cleanup.json` records costs and cleanup without account/token identifiers. An initial cleanup assertion expected an HTTP error for revoked links; the actual documented contract is a 200 tombstone. That assertion was corrected and cleanup completed; no revocation defect was found.

The [manifest](../../../../release-manifests/2026-09-17-main-production-promotion.md) records the full release history, prior accepted native failures, waivers and rollback target. The final evidence is a post-deployment publication; it does not move production main or imply a second deployment.
