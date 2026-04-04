---
description: Infrastructure health check (GCP, Firestore, Alpaca, Book Balancing)
---

**Setup**: Ensure directory exists: `if (!(Test-Path "temp/reports")) { New-Item -ItemType Directory -Path "temp/reports" -Force }`

1. **GCP Health & Logs Check**
   // turbo
   - Check Cloud Run services status for active failures.
   - Fetch last 24h of error logs from Cloud Run to spot silent failures: `gcloud logging read "severity>=ERROR AND resource.type=cloud_run_revision" --limit 10`

2. **The "Book Balancing" Audit (CRITICAL)**
   // turbo
   - Performs a deep reconciliation between Alpaca (Broker) and Firestore (Database).
   - Execute: `poetry run python -m crypto_signals.scripts.diagnostics.book_balancing`
   - **Target Check**: Look specifically for **Reverse Orphans** (Positions open in Alpaca but missing in DB) and **Zombies** (Positions open in DB but missing in Alpaca).

3. **Alpaca Account & State Analysis**
   // turbo
   - Run account status check: `poetry run python -m crypto_signals.scripts.diagnostics.account_status`
   - Verify account balance, buying power, and active exposure.
   - Cross-reference with standard state analysis: `poetry run python -m crypto_signals.scripts.diagnostics.state_analysis`

4. **CI/CD Forensics (Auto-Remediation Prep)**
   // turbo
   - Fetch last failed GitHub Action run: `gh run list --status failed --limit 1 --json databaseId,displayTitle,status,conclusion`
   - Capture failure logs: `gh run view --log-failed`
   - Categorize failure: Flaky Test, Dependency Drift, or Config Gap.

5. **Report Summary**
   - Review all reports. If critical book-balancing errors (Zombies/Orphans) are found, list the offending symbols and propose immediate manual or `/fix` interventions.
