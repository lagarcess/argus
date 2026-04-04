# Infrastructure Health Check Guide

**Last Updated:** December 26, 2025

A quick reference guide for verifying that all Crypto Sentinel GCP infrastructure is properly configured and operational.

## Quick Health Check

Run this single command to verify core components:

```powershell
# Windows PowerShell - Set PATH first if needed
$env:Path = $env:Path + ";C:\Users\YOUR_USERNAME\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin"

# Quick status check
gcloud config get-value project
gcloud run jobs list --region=us-central1
gcloud secrets list --format="table(name)"
gcloud alpha monitoring policies list --format="table(displayName,enabled)"
```

---

## Detailed Verification Commands

### 1. Core Infrastructure & APIs

**Check Project ID:**
```bash
gcloud config list --format='text(core.project)'
```

**Verify Enabled APIs:**
```bash
gcloud services list --enabled --filter="NAME:(run.googleapis.com OR firestore.googleapis.com OR secretmanager.googleapis.com OR artifactregistry.googleapis.com)"
```

*Expected: All 4 services listed as enabled.*

---

### 2. Firestore Database

**Check Database Instance:**
```bash
gcloud firestore databases list
```

*Expected: Database `(default)` with `state: READY`.*

**Check TTL Configuration:**
```bash
gcloud firestore fields ttls list --collection-group=live_signals
```

*Expected: `delete_at` field with `state: ACTIVE`.*

---

### 3. Secret Manager (The Vault)

**List All Secrets:**
```bash
gcloud secrets list --format="table(name, createTime)"
```

*Expected: 5 secrets (ALPACA_API_KEY, ALPACA_SECRET_KEY, TEST_DISCORD_WEBHOOK, LIVE_CRYPTO_DISCORD_WEBHOOK_URL, LIVE_STOCK_DISCORD_WEBHOOK_URL).*

**Verify Secret Has Active Version:**
```bash
gcloud secrets versions list ALPACA_API_KEY
```

*Expected: At least one version with `STATE: enabled`.*

---

### 4. Artifact Registry (Container Images)

**List Repositories:**
```bash
gcloud artifacts repositories list --location=us-central1
```

*Expected: `crypto-signals` repository listed.*

**List Docker Images:**
```bash
gcloud artifacts docker images list us-central1-docker.pkg.dev/$(gcloud config get-value project)/crypto-signals
```

*Expected: At least one image with a recent CREATE_TIME.*

---

### 5. Cloud Run Job

**Describe Job Configuration:**
```bash
gcloud run jobs describe crypto-signals-job --region=us-central1
```

**Key Environment Variables to Verify:**

| Variable | Expected Value | Purpose |
|----------|----------------|---------|
| `TEST_MODE` | `false` | Production mode |
| `ALPACA_PAPER_TRADING` | `true` | Safe paper trading |
| `ENABLE_EXECUTION` | `true` | Allow trade execution |
| `ENABLE_GCP_LOGGING` | `true` | Structured logging |

**Detailed Environment Variables Check:**
```bash
gcloud run jobs describe crypto-signals-job --region=us-central1 --format='yaml(spec.template.spec.template.spec.containers[0].env)'
```

*Verify `ALPACA_PAPER_TRADING` is `true` and `TEST_MODE` is `false`.*

**List Recent Executions:**
```bash
gcloud run jobs executions list --job=crypto-signals-job --region=us-central1 --limit=5
```

---

### 6. Manual Smoke Test

The best way to verify the entire pipeline (Job → Analysis → Firestore → Discord) is to trigger the job manually.

**Run the Job Now:**
```bash
gcloud run jobs execute crypto-signals-job --region=us-central1
```

**Watch Logs in Real-Time:**
After executing, tail the logs to see processing in real-time:
```bash
gcloud alpha logging tail "resource.type=cloud_run_job AND resource.labels.job_name=crypto-signals-job"
```

**What to look for:**
- Initialization logs
- "Fetching bars for BTC/USD" (or other symbols)
- Signal processing messages
- "Job completed" message

### 6a. Automated Performance SLA Check
The smoke test includes an automated latency check for Firestore sector cap queries to ensure execution reliability.

**Query:** `count_open_positions_by_class`
**Threshold:** < 100ms
**Action:** The job will fail (exit 1) if latency exceeds this threshold or if the query fails.

This check ensures that necessary composite indexes are active and performing within the SLA required by the Risk Engine.

> [!TIP]
> Press `Ctrl+C` to stop the log tail when done.

---

### 6b. Python Diagnostic Tools (Local)

For deeper analysis, use the built-in Python diagnostics:

```bash
# Full connectivity check (Alpaca, Firestore, BigQuery, Discord)
poetry run python -m crypto_signals.scripts.diagnostics.health_check

# Account status (balance, open positions, buying power)
poetry run python -m crypto_signals.scripts.diagnostics.account_status

# Firestore state analysis (before/after runs)
poetry run python -m crypto_signals.scripts.diagnostics.state_analysis

# Forensic analysis (detect order gaps between Firestore and Alpaca)
poetry run python -m crypto_signals.scripts.diagnostics.forensic_analysis

# Data Healing (Issue #139)
# Data Healing (Issue #139)
poetry run python -m crypto_signals.scripts.maintenance.resurrect_positions --dry-run
poetry run python -m crypto_signals.scripts.maintenance.fix_reverse_orphans --dry-run
```

Reports are written to `temp/reports/`. See [Scripts Organization](../development/scripts-organization.md) for details.

---

### 7. Monitoring & Alerts

**List Alert Policies:**
```bash
gcloud alpha monitoring policies list --format="table(displayName, name, enabled)"
```

*Expected: Job Failure Alert and High RAM Usage alerts both `True` (enabled).*

**List Notification Channels:**
```bash
gcloud beta monitoring channels list --format="table(displayName, name, type)"
```

*Expected: At least one email notification channel.*

---

### 8. Cloud Scheduler

**Describe Scheduler Job:**
```bash
gcloud scheduler jobs describe crypto-signals-daily --location=us-central1
```

*Expected: Schedule `1 0 * * *` (00:01 UTC daily), state `ENABLED`.*

---

## Summary Checklist

| Component | Command | Expected Result |
|-----------|---------|-----------------|
| **Project** | `gcloud config get-value project` | `crypto-signal-bot-481500` |
| **Cloud Run Job** | `gcloud run jobs list --region=us-central1` | `crypto-signals-job` listed |
| **Secrets** | `gcloud secrets list` | 5 secrets present |
| **Firestore** | `gcloud firestore databases list` | `(default)` is `READY` |
| **Firestore TTL** | `gcloud firestore fields ttls list --collection-group=live_signals` | `delete_at` is `ACTIVE` |
| **Alerts** | `gcloud alpha monitoring policies list` | Policies are `True` |
| **Scheduler** | `gcloud scheduler jobs list --location=us-central1` | `crypto-signals-daily` `ENABLED` |
| **Images** | `gcloud artifacts docker images list ...` | Recent image exists |

---

## Troubleshooting

If any check fails, refer to:
- [GCP Deployment Guide](./deployment-guide.md) - Initial setup steps
- [Troubleshooting Guide](./troubleshooting.md) - Common errors and fixes
- [Production Monitoring](./PRODUCTION_MONITORING.md) - Alert configuration

---

## When to Run Health Checks

| Scenario | Recommended Checks |
|----------|-------------------|
| **After deployment** | Full verification (all sections) |
| **After code changes** | Cloud Run Job, Recent Executions |
| **Daily monitoring** | Quick Health Check, Recent Executions |
| **After alert notification** | Relevant section + logs |
| **Debugging failures** | Full verification + logs review |

---

## View Logs

```bash
# Recent job logs
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=crypto-signals-job" --limit=50

# Error logs only
gcloud logging read "resource.type=cloud_run_job AND severity>=ERROR" --limit=20

# Real-time log streaming
gcloud alpha logging tail "resource.type=cloud_run_job AND resource.labels.job_name=crypto-signals-job"
```

---

## Final Verification Status

Use this table to track your verification progress:

| Milestone | Verification Method | Status |
|-----------|---------------------|--------|
| **Alerting** | `gcloud alpha monitoring policies list` | ⬜ Verified |
| **Infrastructure** | `gcloud run jobs describe` | ⬜ Verified |
| **Firestore** | `gcloud firestore databases list` | ⬜ Verified |
| **Firestore TTL** | `gcloud firestore fields ttls list` | ⬜ Verified |
| **Paper Trading** | Alpaca Web Dashboard | ⬜ Listening |
| **Scheduler** | `gcloud scheduler jobs describe` | ⬜ Verified |
| **Manual Smoke Test** | `gcloud run jobs execute` | ⬜ Completed |
