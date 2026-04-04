# Crypto Sentinel - Deployment Quick Start

**Last Updated:** December 27, 2025

This is a quick-start guide for deploying Crypto Sentinel to Google Cloud Platform. For detailed step-by-step instructions, see the [Complete GCP Deployment Guide](./docs/operations/deployment-guide.md).

## 📚 Documentation

- **[Complete GCP Deployment Guide](./docs/operations/deployment-guide.md)** - Comprehensive deployment instructions with all production details
- **[Troubleshooting Guide](./docs/operations/troubleshooting.md)** - Common errors and solutions from production deployment
- **[GitHub Workflow](./.github/workflows/deploy.yml)** - Automated CI/CD configuration

---

## 🚀 Quick Deployment (5 Minutes)

For users already familiar with GCP and have the prerequisites ready.

### Prerequisites

- ✅ GCP project with billing enabled
- ✅ `gcloud` CLI installed and authenticated
- ✅ Alpaca API credentials (paper or live)
- ✅ Discord webhook URLs
- ✅ GitHub repository admin access

### Phase 1 Foundation (Frontend Auth)

If you are deploying the **Stitch Frontend**, the following manual steps are REQUIRED as modern OAuth providers forbid automated API registration:

1.  **Google OAuth**: Create a Web OAuth Client ID in your GCP Console.
    *   *Redirect URI*: `https://<SUPABASE_ID>.supabase.co/auth/v1/callback`
2.  **GitHub OAuth**: Create a new OAuth App in GitHub Developer Settings.
    *   *Homepage*: `http://localhost:3000`
    *   *Callback*: `https://<SUPABASE_ID>.supabase.co/auth/v1/callback`
3.  **Supabase**: Enable Google and GitHub providers in your Supabase Auth dashboard using the keys from steps 1 & 2.
4.  **Local Env**: Add `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` to your `.env` file.

### Fast-Track Commands

```bash
# 1. Set project variables
export GCP_PROJECT="your-project-id"
export SERVICE_ACCOUNT="crypto-bot-admin@${GCP_PROJECT}.iam.gserviceaccount.com"
gcloud config set project $GCP_PROJECT

# 2. Enable APIs
gcloud services enable run.googleapis.com secretmanager.googleapis.com \
    firestore.googleapis.com cloudscheduler.googleapis.com \
    artifactregistry.googleapis.com logging.googleapis.com bigquery.googleapis.com

# 3. Create infrastructure
gcloud artifacts repositories create crypto-signals \
    --repository-format=docker --location=us-central1
gcloud firestore databases create --location=nam5 --type=firestore-native
bq mk --dataset --location=US ${GCP_PROJECT}:crypto_analytics

# 4. Create service account
gcloud iam service-accounts create crypto-bot-admin \
    --display-name="Crypto Sentinel Bot Admin"

# 5. Grant permissions
for ROLE in run.invoker datastore.user bigquery.dataEditor bigquery.jobUser logging.logWriter; do
  gcloud projects add-iam-policy-binding $GCP_PROJECT \
    --member="serviceAccount:${SERVICE_ACCOUNT}" --role="roles/${ROLE}"
done

# 6. Create secrets (use echo -n to avoid newlines!)
echo -n "YOUR_ALPACA_API_KEY" | gcloud secrets create ALPACA_API_KEY --data-file=-
echo -n "YOUR_ALPACA_SECRET_KEY" | gcloud secrets create ALPACA_SECRET_KEY --data-file=-
echo -n "YOUR_TEST_WEBHOOK" | gcloud secrets create TEST_DISCORD_WEBHOOK --data-file=-
echo -n "YOUR_CRYPTO_WEBHOOK" | gcloud secrets create LIVE_CRYPTO_DISCORD_WEBHOOK_URL --data-file=-
echo -n "YOUR_STOCK_WEBHOOK" | gcloud secrets create LIVE_STOCK_DISCORD_WEBHOOK_URL --data-file=-

# 7. Grant secret access
for SECRET in ALPACA_API_KEY ALPACA_SECRET_KEY TEST_DISCORD_WEBHOOK \
    LIVE_CRYPTO_DISCORD_WEBHOOK_URL LIVE_STOCK_DISCORD_WEBHOOK_URL; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
done

# 8. Create placeholder Cloud Run job
gcloud run jobs create crypto-signals-job \
    --region=us-central1 \
    --image=us-docker.pkg.dev/cloudrun/container/placeholder \
    --service-account="${SERVICE_ACCOUNT}" \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=${GCP_PROJECT}"

# 9. Create Cloud Scheduler (daily at 00:01 UTC)
# IMPORTANT: Use the regional endpoint format for v1 API
gcloud scheduler jobs create http crypto-signals-daily \
    --location=us-central1 \
    --schedule="1 0 * * *" \
    --time-zone="UTC" \
    --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${GCP_PROJECT}/jobs/crypto-signals-job:run" \
    --http-method=POST \
    --oauth-service-account-email="${SERVICE_ACCOUNT}" \
    --description="Capture daily crypto candle closes at 00:01 UTC"

# 10. Grant run.invoker on the Cloud Run job (required for scheduler)
gcloud run jobs add-iam-policy-binding crypto-signals-job \
    --region=us-central1 \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/run.invoker"

# 11. Create service account key for GitHub
gcloud iam service-accounts keys create ~/crypto-bot-key.json \
    --iam-account="${SERVICE_ACCOUNT}"
cat ~/crypto-bot-key.json  # Copy this to GitHub Secrets
rm ~/crypto-bot-key.json

echo "✅ GCP infrastructure setup complete!"
echo "Next: Configure GitHub Secrets and Variables (see docs/operations/deployment-guide.md#6-github-repository-configuration)"
```

---

## 🔧 GitHub Configuration

### Required Secrets

Go to **Settings → Secrets and variables → Actions → Repository secrets**:

| Secret                           | Value                                                                 |
| -------------------------------- | --------------------------------------------------------------------- |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service account JSON key (from step 10 above)                         |
| `GAR_REPOSITORY`                 | `us-central1-docker.pkg.dev/PROJECT-ID/crypto-signals/crypto-signals` |
| `ALPACA_API_KEY`                 | Your Alpaca API key                                                   |
| `ALPACA_SECRET_KEY`              | Your Alpaca secret key                                                |
| `TEST_DISCORD_WEBHOOK`           | Test Discord webhook URL                                              |
| `DISCORD_DEPLOYS`                | **NEW** - Deployment notification webhook                             |

### Required Variables

Go to **Settings → Secrets and variables → Actions → Repository variables**:

| Variable                 | Value             |
| ------------------------ | ----------------- |
| `GOOGLE_CLOUD_PROJECT`   | `your-project-id` |
| `GCP_REGION`             | `us-central1`     |
| `TEST_MODE`              | `false`           |
| `ALPACA_PAPER_TRADING`   | `true`            |
| `ENABLE_EXECUTION`       | `true`            |
| `ENABLE_EQUITIES`        | `false`           |
| `ENABLE_GCP_LOGGING`     | `true`            |
| `DISABLE_SECRET_MANAGER` | `false`           |

---

## ✅ Verification

 ### BigQuery Schema Migration (Issue 116)

 If you encounter errors about missing columns (e.g., `buying_power`), you may need to manually update the BigQuery schema.

 1. Check `scripts/schema_migration.sql` ensuring it uses `{{PROJECT_ID}}`.
 2. Run the migration utility (injects credentials automatically):
    ```bash
    poetry run python scripts/run_migration.py
    ```

 ### Firestore Index Verification (Issue 127)

 Ensure the sector cap composite index is active to prevent performance degradation.
 See [Verification Steps](./docs/operations/deployment-guide.md#verification-steps) in the deployment guide.

 ### Verification Commands

```bash
# Test manual execution
gcloud run jobs execute crypto-signals-job --region=us-central1 --wait

# Test scheduler
gcloud scheduler jobs run crypto-signals-daily --location=us-central1

# View logs
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=crypto-signals-job" --limit=20

# Check next scheduled run
gcloud scheduler jobs describe crypto-signals-daily --location=us-central1
```

---

## 📋 Deployment Overview

### Architecture

```
GitHub Actions (CI/CD)
    ↓
Artifact Registry (Docker images)
    ↓
Cloud Run Job (executes trading bot)
    ↓
├── Secret Manager (credentials)
├── Firestore (signal storage)
├── BigQuery (trade analytics)
└── Discord (notifications)
    ↑
Cloud Scheduler (daily 00:01 UTC)
```

### Workflow

1. **Push to `main` branch** → Triggers GitHub Actions
2. **CI Job** → Lint, test, security audit
3. **Validate Deployment** → Dry-run configuration checks (PRs only)
4. **CD Job** → Build Docker image, push to Artifact Registry, update Cloud Run job
5. **Smoke Test** → Execute job with `--smoke-test` flag to verify connectivity
6. **Auto-Rollback** → Revert to `latest` if smoke test fails
7. **Promote to Latest** → Tag new image as `latest` only after smoke test passes
8. **Cloud Scheduler** → Triggers job daily at 00:01 UTC
9. **Cloud Run Job** → Analyzes markets, generates signals, executes trades
   - **State Reconciliation** (new): At startup, detects and heals sync gaps between Alpaca and Firestore
     - Heals **Zombies**: Positions marked OPEN in DB but closed in Alpaca → marks `CLOSED_EXTERNALLY`
     - Alerts **Orphans**: Positions open in Alpaca but missing from DB → sends Discord alert
10. **Nightly Archival** → Archives closed trades and theoretical signals to BigQuery
11. **Notifications** → Success/failure sent to Discord

### CI/CD Features

**Concurrency Control:**

- Only one deployment runs at a time (`cancel-in-progress: true`)
- Prevents race conditions and conflicting deployments

**Smoke Testing:**

- After deployment, executes job with `--smoke-test` flag
- Verifies Firestore connectivity and configuration
- Skips full signal generation for fast validation

**Auto-Rollback:**

- If smoke test fails, automatically reverts to previous `latest` image
- Uses "Promote-on-Success" pattern: `latest` tag only applied after passing smoke test
- Failed builds are never promoted, ensuring `latest` always points to a stable release

**Bypass Logic:**

- Add `[skip-smoke]` to commit message to skip smoke test
- Useful for documentation-only changes or emergency hotfixes
- Image still promoted to `latest` if deployment succeeds

**Detailed Notifications:**

- Discord notifications include process summary with status emojis:
  - Build & Deploy: 🟢 Passed / 🔴 Failed
  - Smoke Test: 🟢 Passed / 🔴 Failed / ⏭️ Skipped
- Granular error reporting with last 5 lines of validation errors

---

## 🆘 Troubleshooting

### Common Errors

| Error                        | Solution                                                                                   |
| ---------------------------- | ------------------------------------------------------------------------------------------ |
| Permission denied on secret  | [Grant secretAccessor role](./docs/operations/troubleshooting.md#error-1-permission-denied-on-secret) |
| Missing GOOGLE_CLOUD_PROJECT | [Add environment variable](./docs/operations/troubleshooting.md#error-2-missing-google_cloud_project) |
| Boolean parsing error        | [Remove trailing newlines](./docs/operations/troubleshooting.md#error-3-boolean-parsing-error)        |
| Missing Docker image name    | [Set GAR_REPOSITORY secret](./docs/operations/troubleshooting.md#error-4-missing-docker-image-name)   |
| Invalid scheduler URI        | [Use correct URI format](./docs/operations/troubleshooting.md#error-5-invalid-scheduler-uri)          |

**See the complete [Troubleshooting Guide](./docs/operations/troubleshooting.md) for detailed solutions.**

### Quick Debug Commands

```bash
# View recent errors
gcloud logging read "resource.type=cloud_run_job AND severity>=ERROR" --limit=10

# Check job config
gcloud run jobs describe crypto-signals-job --region=us-central1

# Verify secrets
gcloud secrets get-iam-policy ALPACA_API_KEY

# List executions
gcloud run jobs executions list --job=crypto-signals-job --region=us-central1
```

---

## 📖 Detailed Documentation

For comprehensive deployment instructions:

- **[Complete GCP Deployment Guide](./docs/operations/deployment-guide.md)** - Step-by-step deployment with all production details including:
  - Service account configuration
  - Secret Manager setup with permission granting
  - Cloud Scheduler configuration for 00:01 UTC
  - All environment variables and their purposes
  - Complete verification procedures

- **[Troubleshooting Guide](./docs/operations/troubleshooting.md)** - Real production errors and solutions:
  - 5+ documented errors with full solutions
  - Debugging commands for each scenario
  - How to view logs and check status
  - Common workflow failures

---

## 🔐 Security Best Practices

- ✅ Never commit secrets to git
- ✅ Use `echo -n` when creating secrets (no newlines)
- ✅ Rotate API keys regularly
- ✅ Use custom service account (not default)
- ✅ Grant minimal IAM permissions
- ✅ Enable GCP logging for audit trail
- ✅ Use paper trading API in production

---

## 💰 Cost Optimization

- **Cloud Run Jobs:** Pay per execution (~$0.01-0.05 per run)
- **Firestore:** Free tier covers most usage
- **BigQuery:** Free tier for analytics queries
- **Secret Manager:** ~$0.06 per secret per month
- **Estimated Monthly Cost:** $5-15 for daily execution

---

## 📝 Production Deployment Info

**Validated:** December 26, 2025
**Service Account:** `crypto-bot-admin@crypto-signal-bot-481500.iam.gserviceaccount.com`
**Schedule:** Daily at 00:01 UTC
**Region:** us-central1

All deployment steps and troubleshooting scenarios have been validated through actual production deployment.

---

**Need Help?** Check the [Troubleshooting Guide](./docs/operations/troubleshooting.md) or open an issue on GitHub.
