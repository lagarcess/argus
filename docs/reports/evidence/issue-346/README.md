# Issue 346 guest quota recovery evidence

This directory contains the exact-head local-Supabase browser captures for the
guest simulation exhaustion recovery modal.

- `guest-quota-recovery-en.png` verifies the English reset-time and conversion
  offer after the two-simulation allowance is exhausted.
- `guest-quota-recovery-es-419.png` verifies the equivalent Spanish surface.

Capture command (with the candidate SHA pinned at execution):

```bash
ARGUS_EXPECTED_CANDIDATE_SHA="$(git rev-parse HEAD)" \
  ARGUS_GUEST_QA_APP_PORT=59900 \
  ARGUS_GUEST_QA_API_PORT=59901 \
  bash scripts/qa/run-guest-experience-qa.sh preflight \
  --grep "exhausted guest simulation"
```

The gate builds the production frontend, uses only the disposable local
Supabase stack, and runs the English and Spanish checks serially.
