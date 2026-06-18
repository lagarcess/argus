# Private Alpha Release Manifest Template

Use one manifest per promoted candidate. Fill this after the release gate passes
and before sending tester links. Do not include raw conversation, user, run, or
job ids; use the privacy-safe labels from canary evidence.

## Candidate

- Candidate SHA:
- Candidate branch:
- Promotion target: `main`
- Release captain:
- Approver:
- Rollback target:
- Decision record:

## Deploy Proof

- API service: `argus-api`
- API deploy status:
- API deployed SHA:
- Web service: `argus-app`
- Web deploy status:
- Web deployed SHA:
- Checked at:

## Environment Proof

- Expected mode:
- api_web_env_fingerprint:
- env_fingerprint script output:
- workflow_task:
- real_workflow_task:
- Backtest service mode:
- Workflow service proof:
  - `argus-backtests` latest deploy/status:
  - active workflow task verified:
  - real workflow task verified:
- Feature flags:
- Render config audit command:
- Secret rotation / least-privilege owner:

## Gate Evidence

- Local smoke command:
- Local smoke result:
- Warmup command:
- Warmup result:
- Canary evidence artifact: `private-alpha-canary-evidence`
- English canary:
  - JSON evidence:
  - Exit status:
- Spanish canary:
  - JSON evidence:
  - Exit status:
- Browser QA, if applicable:

## Release Decision

- Public tester exposure approved:
- Known caveats:
- Rollback trigger:
- Rollback command or owner:
- Follow-up owner:

## Privacy Notes

- No raw conversation, user, run, or job ids.
- Canary labels are stable hashes for audit correlation only.
- Service-role credentials, cookies, prompts, and route receipt payloads are not
  copied into this manifest.
