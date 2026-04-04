# GCP Deployment Guide: Crypto Sentinel

**Last Updated:** December 27, 2025
**Production Validated:** ✅ December 27, 2025

This guide documents the complete production deployment process for Crypto Sentinel on Google Cloud Platform. All steps have been validated through actual production deployment, including Cloud Scheduler configuration for daily 00:01 UTC execution.

## Table of Contents

- [Prerequisites](#prerequisites)
  - [Windows gcloud CLI Setup](#windows-gcloud-cli-setup)
- [1. GCP Infrastructure Setup](#1-gcp-infrastructure-setup)
  - [1.1. Enable Required APIs](#11-enable-required-apis)
  - [1.2. Create Artifact Registry](#12-create-artifact-registry)
  - [1.3. Initialize Firestore](#13-initialize-firestore)
  - [1.4. Configure Firestore Indexes](#14-configure-firestore-indexes)
  - [1.5. Initialize BigQuery](#15-initialize-bigquery)
- [2. Service Account Configuration](#2-service-account-configuration)
  - [2.1. Create Custom Service Account (Recommended)](#21-create-custom-service-account-recommended)
  - [2.2. Grant Required Permissions](#22-grant-required-permissions)
- [3. Secret Manager Setup](#3-secret-manager-setup)
  - [3.1. Create Secrets](#31-create-secrets)
  - [3.2. Grant Secret Access to Service Account](#32-grant-secret-access-to-service-account)
- [4. Cloud Run Job Deployment](#4-cloud-run-job-deployment)
  - [4.1. Create Initial Placeholder Job](#41-create-initial-placeholder-job)
  - [4.2. Deploy Production Image](#42-deploy-production-image)
- [5. Cloud Scheduler Configuration](#5-cloud-scheduler-configuration)
  - [5.1. Create Daily Scheduler (00:01 UTC)](#51-create-daily-scheduler-0001-utc)
  - [5.2. Verify Next Run Time](#52-verify-next-run-time)
- [6. GitHub Repository Configuration](#6-github-repository-configuration)
  - [6.1. Repository Secrets](#61-repository-secrets)
  - [6.2. Repository Variables](#62-repository-variables)
- [7. Verification and Testing](#7-verification-and-testing)
  - [7.1. Test Manual Execution](#71-test-manual-execution)
  - [7.2. Test Scheduler](#72-test-scheduler)
  - [7.3. Verify Firestore Data](#73-verify-firestore-data)
  - [7.4. Check Discord Notifications](#74-check-discord-notifications)
- [8. Production Deployment Checklist](#8-production-deployment-checklist)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting the deployment, ensure you have:

1. **Google Cloud Platform Account**
   - Active GCP project with billing enabled
   - Project ID (e.g., `crypto-signal-bot-481500`)

2. **Local Tools Installed**
   - `gcloud` CLI (see [Windows Setup](#windows-gcloud-cli-setup) or [Installation Guide](https://cloud.google.com/sdk/docs/install))
   - `git`
   - `docker` (for local testing)

3. **Permissions**
   - GCP Project Owner or Editor role
   - Ability to create service accounts and grant IAM permissions

4. **API Credentials**
   - Alpaca API Key and Secret (Paper or Live trading)
   - Discord Webhook URLs for notifications

5. **GitHub Repository Access**
   - Admin permissions to set Secrets and Variables
   - Ability to create/push to branches

---

### Windows gcloud CLI Setup

This section covers installing and configuring the Google Cloud SDK on Windows.

#### Step 1: Install Google Cloud SDK

**Option A: Using winget (Recommended)**

```powershell
# Install Google Cloud SDK via winget
winget install Google.CloudSDK --accept-package-agreements --accept-source-agreements
```

**Option B: Using the Installer**

1. Download the installer from [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
2. Run `GoogleCloudSDKInstaller.exe`
3. Check the option to **add gcloud to your PATH**
4. Complete the installation wizard

#### Step 2: Refresh PATH (PowerShell)

After installation, refresh your PATH to use `gcloud` immediately without restarting:

```powershell
# Refresh PATH in current PowerShell session
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# Verify installation
gcloud --version
```

**Expected output:**
```
Google Cloud SDK 550.0.0
bq 2.1.26
core 2025.12.12
gcloud-crc32c 1.0.0
gsutil 5.35
```

#### Step 3: Authenticate with Google Cloud

```powershell
# Login to Google Cloud (opens browser)
gcloud auth login
```

This opens a browser window:
1. Sign in with your Google account that has GCP access
2. Click **Allow** to grant permissions
3. Return to the terminal - you should see "You are now logged in as [your-email]"

#### Step 4: Set Your Project

```powershell
# Set your GCP project
gcloud config set project crypto-signal-bot-481500

# Verify configuration
gcloud config list
```

#### Step 5: Running Bash Scripts on Windows

The `scripts/setup_gcp.sh` script is a bash script. On Windows, you have several options:

**Option A: Run Commands Directly in PowerShell**

Instead of running the bash script, execute the gcloud commands directly:

```powershell
# Set project
gcloud config set project crypto-signal-bot-481500

# Enable APIs
gcloud services enable `
    run.googleapis.com `
    secretmanager.googleapis.com `
    firestore.googleapis.com `
    cloudscheduler.googleapis.com `
    artifactregistry.googleapis.com `
    logging.googleapis.com `
    bigquery.googleapis.com

# Create Artifact Registry (skip if exists)
gcloud artifacts repositories create crypto-signals `
    --repository-format=docker `
    --location=us-central1 `
    --description="Crypto Sentinel Docker images"

# Check Firestore (create if needed via Console)
gcloud firestore databases describe
```

**Option B: Use Git Bash**

If you have Git installed, Git Bash can run the script:

```bash
# In Git Bash terminal
./scripts/setup_gcp.sh crypto-signal-bot-481500
```

**Option C: Use WSL (Windows Subsystem for Linux)**

```bash
# In WSL terminal
bash scripts/setup_gcp.sh crypto-signal-bot-481500
```

> [!TIP]
> For one-time setup, running commands directly in PowerShell is often simpler than setting up bash environments.

---

## 1. GCP Infrastructure Setup

All commands should be run in Google Cloud Shell or with `gcloud` CLI authenticated.

### 1.1. Enable Required APIs

Enable all necessary Google Cloud APIs for the project:

```bash
# Set your project ID
export GCP_PROJECT="your-project-id"
gcloud config set project $GCP_PROJECT

# Enable all required APIs
gcloud services enable \
    run.googleapis.com \
    secretmanager.googleapis.com \
    firestore.googleapis.com \
    cloudscheduler.googleapis.com \
    artifactregistry.googleapis.com \
    logging.googleapis.com \
    bigquery.googleapis.com \
    iam.googleapis.com
```

**Verification:**

```bash
gcloud services list --enabled
```

---

### 1.2. Create Artifact Registry

Create a Docker repository to store container images:

```bash
gcloud artifacts repositories create crypto-signals \
    --repository-format=docker \
    --location=us-central1 \
    --description="Crypto Sentinel Docker images"
```

**Verification:**

```bash
gcloud artifacts repositories list --location=us-central1

# Expected output:
# REPOSITORY      FORMAT  MODE                 DESCRIPTION                       LOCATION      LABELS  ENCRYPTION
# crypto-signals  DOCKER  STANDARD_REPOSITORY  Crypto Sentinel Docker images    us-central1           Google-managed key
```

---

### 1.3. Initialize Firestore

Firestore must be initialized in **Native Mode**:

**Option A: Via Console (Recommended for first-time users)**
1. Go to [Firestore Console](https://console.cloud.google.com/firestore)
2. Click **Create Database**
3. Select **Native Mode**
4. Choose location: `nam5 (United States)` or `us-central1`
5. Click **Create**

**Option B: Via gcloud CLI**

```bash
gcloud firestore databases create \
    --location=nam5 \
    --type=firestore-native
```

**Verification:**

```bash
gcloud firestore databases list
```


### 1.4. Configure Firestore Indexes

The Risk Engine requires a **Composite Index** to efficiently enforce sector caps (`MAX_CRYPTO_POSITIONS`). Without this, the application will crash with a GRPC Error.

**Run this command to create the index:**

```bash
gcloud firestore indexes composite create \
    --collection-group=live_positions \
    --field-config field-path=status,order=ascending \
    --field-config field-path=asset_class,order=ascending
```

*Note: Index creation can take 5-10 minutes.*

#### Verification Steps

Operators should confirm that the index is created and being used to avoid silent performance degradation.

**1. Check Index Status**

Ensure the index is in `READY` state:

```bash
gcloud firestore indexes composite list --filter="collectionGroup=live_positions"
```

**2. Verify Index Usage (Query Execution Plan)**

To confirm the index is being used (and not falling back to a full table scan), you can use the Firestore execution plan in the GCP Console:

1. Go to **Firestore Studio** > **Query Builder**.
2. Construct a query:
   - Collection: `live_positions`
   - Filter: `status` == `OPEN`
   - Filter: `asset_class` == `CRYPTO`
3. Click **Explain** (instead of Run).
4. Verify that the **Plan Summary** shows usage of the composite index.

**3. Monitor Performance**

The Risk Engine performs a sector cap check before every trade.
- **Metric:** Track query latency for `count_open_positions_by_class`.
- **Alert Threshold:** > 100ms
- **Impact:** Slow checks can cause slippage or timeout errors.

If latency spikes, verify the index is still present and `READY`.

---

### 1.5. Initialize BigQuery

BigQuery is used for trade archival and analytics:

```bash
# Create dataset for trade history
bq --location=US mk \
    --dataset \
    --description "Crypto Sentinel trade history" \
    ${GCP_PROJECT}:crypto_signals
```

**Verification:**

```bash
bq ls
```

---

### 1.6. Phase 1 Authentication (OAuth & Supabase)

Required for the Stitch React Frontend. Because Google and GitHub forbid automated API registration via third-party agents, these steps must be performed manually.

#### 1.6.1. Google OAuth Registration
1. Go to **APIs & Services** > **Credentials**.
2. Click **Create Credentials** > **OAuth client ID**.
3. **Application Type**: Web application.
4. **Authorized Redirect URIs**: `https://[SUPABASE_ID].supabase.co/auth/v1/callback`
5. Save the generated **Client ID** and **Client Secret**.

#### 1.6.2. GitHub OAuth Registration
1. Go to [GitHub Developer Settings](https://github.com/settings/developers) > **OAuth Apps**.
2. **Homepage URL**: `http://localhost:3000` (for local development).
3. **Authorization callback URL**: `https://[SUPABASE_ID].supabase.co/auth/v1/callback`
4. Generate a **Client Secret** and save it alongside the **Client ID**.

#### 1.6.3. Supabase Provider Linkage
1. Open your project in the [Supabase Dashboard](https://supabase.com/dashboard).
2. Go to **Authentication** > **Providers**.
3. Enable **Google** and **GitHub** toggles.
4. Paste the respective Client IDs and Secrets from Google and GitHub.

---

---

## 2. Service Account Configuration

### 2.1. Create Custom Service Account (Recommended)

Using a custom service account provides better security and auditability:

```bash
# Create service account
gcloud iam service-accounts create crypto-bot-admin \
    --display-name="Crypto Sentinel Bot Admin" \
    --description="Service account for Crypto Sentinel Cloud Run jobs"

# Store service account email
export SERVICE_ACCOUNT="crypto-bot-admin@${GCP_PROJECT}.iam.gserviceaccount.com"
echo "Service account: $SERVICE_ACCOUNT"
```

**Alternative: Use Default Compute Service Account**

If you prefer to use the default service account:

```bash
export PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT --format='value(projectNumber)')
export SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
```

---

### 2.2. Grant Required Permissions

Grant the service account permissions to access GCP services:

```bash
# Cloud Run Invoker (for scheduler to trigger job)
gcloud projects add-iam-policy-binding $GCP_PROJECT \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/run.invoker"

# Firestore User (read/write access to Firestore)
gcloud projects add-iam-policy-binding $GCP_PROJECT \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/datastore.user"

# BigQuery Data Editor (write access to BigQuery)
gcloud projects add-iam-policy-binding $GCP_PROJECT \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/bigquery.dataEditor"

# BigQuery Job User (run queries)
gcloud projects add-iam-policy-binding $GCP_PROJECT \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/bigquery.jobUser"

# Logs Writer (write to Cloud Logging)
gcloud projects add-iam-policy-binding $GCP_PROJECT \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/logging.logWriter"
```

**Verification:**

```bash
gcloud projects get-iam-policy $GCP_PROJECT \
    --flatten="bindings[].members" \
    --filter="bindings.members:${SERVICE_ACCOUNT}"
```

---

## 3. Secret Manager Setup

### 3.1. Create Secrets

Store all sensitive credentials in Google Secret Manager. **Important:** Use `echo -n` to avoid trailing newlines that cause parsing errors.

```bash
# Alpaca API credentials
echo -n "YOUR_ALPACA_API_KEY" | gcloud secrets create ALPACA_API_KEY --data-file=-
echo -n "YOUR_ALPACA_SECRET_KEY" | gcloud secrets create ALPACA_SECRET_KEY --data-file=-

# Discord webhooks
echo -n "https://discord.com/api/webhooks/YOUR_TEST_WEBHOOK" | gcloud secrets create TEST_DISCORD_WEBHOOK --data-file=-
echo -n "https://discord.com/api/webhooks/YOUR_CRYPTO_WEBHOOK" | gcloud secrets create LIVE_CRYPTO_DISCORD_WEBHOOK_URL --data-file=-
echo -n "https://discord.com/api/webhooks/YOUR_STOCK_WEBHOOK" | gcloud secrets create LIVE_STOCK_DISCORD_WEBHOOK_URL --data-file=-

# Discord Bot Token (for thread recovery feature)
echo -n "YOUR_DISCORD_BOT_TOKEN" | gcloud secrets create DISCORD_BOT_TOKEN --data-file=-
```

**Verification:**

```bash
gcloud secrets list

# Verify no trailing newlines (should show clean values)
gcloud secrets versions access latest --secret=ALPACA_API_KEY | od -c
```

**Batch Verify All Secrets Exist:**

```bash
for secret in ALPACA_API_KEY ALPACA_SECRET_KEY TEST_DISCORD_WEBHOOK \
  LIVE_CRYPTO_DISCORD_WEBHOOK_URL LIVE_STOCK_DISCORD_WEBHOOK_URL \
  DISCORD_SHADOW_WEBHOOK_URL DISCORD_BOT_TOKEN; do
    gcloud secrets describe $secret > /dev/null 2>&1 && \
    echo "✅ $secret exists" || echo "❌ $secret MISSING";
done
```

⚠️ **Common Pitfall:** Using `echo` without `-n` adds a newline character (`\n`), causing Pydantic validation errors like:
```
Input should be a valid boolean, unable to interpret input [type=bool_parsing, input_value='true\r\n']
```

---

### 3.2. Grant Secret Access to Service Account

Grant the service account permission to access all secrets:

```bash
# Grant access to each secret
for SECRET in ALPACA_API_KEY ALPACA_SECRET_KEY TEST_DISCORD_WEBHOOK LIVE_CRYPTO_DISCORD_WEBHOOK_URL LIVE_STOCK_DISCORD_WEBHOOK_URL DISCORD_BOT_TOKEN; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
done
```

**Verification:**

```bash
# Check permissions on a secret
gcloud secrets get-iam-policy ALPACA_API_KEY

# Expected output should show your service account with secretAccessor role
```

⚠️ **Critical:** Without this step, Cloud Run will fail with:
```
Permission denied on secret: projects/.../secrets/ALPACA_API_KEY/versions/latest
```

See [Troubleshooting Guide](./troubleshooting.md#error-1-permission-denied-on-secret) for details.

---

## 4. Cloud Run Job Deployment

### 4.1. Create Initial Placeholder Job

For the first deployment, create a placeholder job that GitHub Actions will update:

```bash
gcloud run jobs create crypto-signals-job \
    --region=us-central1 \
    --image=us-docker.pkg.dev/cloudrun/container/placeholder \
    --service-account="${SERVICE_ACCOUNT}" \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=${GCP_PROJECT}"
```

**Why a placeholder?**
- GitHub Actions workflow uses `gcloud run jobs update`, which requires an existing job
- The placeholder creates the job structure that CI/CD will populate

---

### 4.2. Deploy Production Image

After setting up GitHub Actions (see [Section 6](#6-github-repository-configuration)), the workflow will automatically deploy. For manual deployment:

```bash
# Build and push image manually
export IMAGE_TAG="us-central1-docker.pkg.dev/${GCP_PROJECT}/crypto-signals/crypto-signals:latest"

# Authenticate Docker to Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build image
docker build -t $IMAGE_TAG .

# Push to registry
docker push $IMAGE_TAG

# Update Cloud Run job
gcloud run jobs update crypto-signals-job \
    --region=us-central1 \
    --image="${IMAGE_TAG}" \
    --service-account="${SERVICE_ACCOUNT}" \
    --max-retries=1 \
    --task-timeout=10m \
    --memory=1Gi \
    --cpu=1 \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=${GCP_PROJECT},TEST_MODE=false,ALPACA_PAPER_TRADING=true,ENABLE_EXECUTION=true,ENABLE_EQUITIES=false,ENABLE_GCP_LOGGING=true" \
    --set-secrets="ALPACA_API_KEY=ALPACA_API_KEY:latest,ALPACA_SECRET_KEY=ALPACA_SECRET_KEY:latest,TEST_DISCORD_WEBHOOK=TEST_DISCORD_WEBHOOK:latest,LIVE_CRYPTO_DISCORD_WEBHOOK_URL=LIVE_CRYPTO_DISCORD_WEBHOOK_URL:latest,LIVE_STOCK_DISCORD_WEBHOOK_URL=LIVE_STOCK_DISCORD_WEBHOOK_URL:latest"
```

**Environment Variables Explained:**

| Variable | Value | Purpose |
|----------|-------|---------|
| `GOOGLE_CLOUD_PROJECT` | `your-project-id` | **REQUIRED** - Project ID for GCP services |
| `ENVIRONMENT` | `PROD` or `DEV` | **NEW** - Controls DB routing and Execution Gating (Default: `DEV`) |
| `TEST_MODE` | `false` | Enables real Discord notifications (should be `false` for production) |
| `ALPACA_PAPER_TRADING` | `true` | Uses Alpaca paper trading API |
| `ENABLE_EXECUTION` | `true` | Enables order submission (Gated by `ENVIRONMENT=PROD`) |
| `ENABLE_EQUITIES` | `false` | Disables stock trading (crypto only) |
| `ENABLE_GCP_LOGGING` | `true` | Enables structured JSON logging |

### 4.3. Environment Isolation & Execution Gating

The application implements strict isolation between Production and Development/Test environments to prevent accidental trades and data contamination.

**1. Database Routing:**
Based on the `ENVIRONMENT` variable, repositories route traffic to different collections:
- **PROD**: `live_signals`, `live_positions`, `rejected_signals`
- **DEV**: `test_signals`, `test_positions`, `test_rejected_signals`

**2. Execution Gating (Safety Mechanism):**
The `ExecutionEngine` includes a hard gate:
- If `ENVIRONMENT=PROD` AND `ENABLE_EXECUTION=true`: Trades are submitted to Alpaca.
- If `ENVIRONMENT=DEV`: All trading operations are skipped and logged as `[THEORETICAL MODE]`.
- This ensures that local development or experimental Cloud Run jobs NEVER interact with your trading capital.

⚠️ **Critical:** `GOOGLE_CLOUD_PROJECT` is required. Without it, you'll get:
```
ValidationError: 1 validation error for Settings
GOOGLE_CLOUD_PROJECT
  Field required
```

---

## 5. Cloud Scheduler Configuration

### 5.1. Create Daily Scheduler (00:01 UTC)

Configure Cloud Scheduler to trigger the job daily at 00:01 UTC to capture crypto daily candle closes:

```bash
# Enable Cloud Scheduler API (if not already enabled)
gcloud services enable cloudscheduler.googleapis.com

# Create scheduler job for daily 00:01 UTC execution
# IMPORTANT: Use the regional endpoint format for v1 API
gcloud scheduler jobs create http crypto-signals-daily \
    --location=us-central1 \
    --schedule="1 0 * * *" \
    --time-zone="UTC" \
    --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${GCP_PROJECT}/jobs/crypto-signals-job:run" \
    --http-method=POST \
    --oauth-service-account-email="${SERVICE_ACCOUNT}" \
    --description="Capture daily crypto candle closes at 00:01 UTC"

# REQUIRED: Grant run.invoker on the Cloud Run job itself
# Without this, the scheduler will fail with status code 5 (NOT_FOUND)
gcloud run jobs add-iam-policy-binding crypto-signals-job \
    --region=us-central1 \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/run.invoker"
```

**Cron Schedule Explained:**
- `1 0 * * *` = minute 1, hour 0, every day, every month, every weekday
- Executes at 00:01 UTC daily
- Time zone: UTC (critical for crypto markets)

**Alternative Schedules:**

```bash
# Every 4 hours
--schedule="0 */4 * * *"

# Every day at 9 AM UTC
--schedule="0 9 * * *"

# Weekdays only at 00:01 UTC
--schedule="1 0 * * 1-5"

# Every Sunday at 00:01 UTC (weekly)
--schedule="1 0 * * 0"
```

⚠️ **URI Format is Critical:**

**Correct format (uses regional endpoint for v1 API):**
```
https://{REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/{PROJECT-ID}/jobs/{JOB-NAME}:run
```

**Incorrect format (will fail with status code 5 NOT_FOUND):**
```
https://run.googleapis.com/v1/projects/{PROJECT-ID}/locations/{REGION}/jobs/{JOB-NAME}:run
```

> [!IMPORTANT]
> You must also grant `roles/run.invoker` on the Cloud Run job itself (not just at the project level). Without this, the scheduler trigger will fail with `status.code: 5` (NOT_FOUND).

See [Troubleshooting Guide](./troubleshooting.md#error-5-invalid-scheduler-uri) for details.

---

### 5.2. Verify Next Run Time

```bash
# Check scheduler configuration
gcloud scheduler jobs describe crypto-signals-daily --location=us-central1

# View schedule and state
gcloud scheduler jobs describe crypto-signals-daily \
    --location=us-central1 \
    --format="table(schedule, timeZone, state)"

# Test scheduler manually
gcloud scheduler jobs run crypto-signals-daily --location=us-central1
```

**Expected output:**
```
SCHEDULE     TIME_ZONE  STATE
1 0 * * *    UTC        ENABLED
```

**Pause/Resume Scheduler:**

```bash
# Pause scheduler
gcloud scheduler jobs pause crypto-signals-daily --location=us-central1

# Resume scheduler
gcloud scheduler jobs resume crypto-signals-daily --location=us-central1
```

**Configure Retry Policy:**

```bash
# Recommended: 1 retry with 5-minute backoff
gcloud scheduler jobs update http crypto-signals-daily \
  --location=us-central1 \
  --max-retry-attempts=1 \
  --max-retry-duration=600s \
  --min-backoff=300s \
  --max-backoff=300s
```

**Retry Behavior:**
- Initial failure → Wait 5 minutes → Retry once
- Total failure detection time: ~10 minutes
- Handles transient API/network issues without masking code bugs

---

## 6. GitHub Repository Configuration

Configure GitHub repository for automated CI/CD deployment.

### 6.1. Repository Secrets

Go to **Settings → Secrets and variables → Actions → Repository secrets** and add:

| Secret Name | Value | Purpose |
|-------------|-------|---------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Service account JSON key | GCP authentication for GitHub Actions |
| `GAR_REPOSITORY` | `us-central1-docker.pkg.dev/PROJECT-ID/crypto-signals/crypto-signals` | Artifact Registry image path |
| `ALPACA_API_KEY` | Your Alpaca API key | Used for CI tests |
| `ALPACA_SECRET_KEY` | Your Alpaca secret key | Used for CI tests |
| `TEST_DISCORD_WEBHOOK` | Test webhook URL | Used for CI tests |
| `DISCORD_DEPLOYS` | Deployment notification webhook | **NEW** - CI/CD deployment notifications |

**Creating Service Account JSON Key:**

```bash
# Create key for service account
gcloud iam service-accounts keys create ~/crypto-bot-key.json \
    --iam-account="${SERVICE_ACCOUNT}"

# Display key content (copy this to GitHub secret)
cat ~/crypto-bot-key.json

# Delete local key file after copying
rm ~/crypto-bot-key.json
```

⚠️ **Security:** Never commit service account keys to git. Always use GitHub Secrets.

**`DISCORD_DEPLOYS` Webhook Setup:**

This webhook receives notifications for successful/failed deployments:
1. Create a Discord channel for deployment notifications
2. Create a webhook for that channel
3. Add the webhook URL to GitHub secrets as `DISCORD_DEPLOYS`

Notification example:
```
✅ Deployment successful!
CD Pipeline Success
Commit: abc123...
Author: username
```

---

### 6.2. Repository Variables

Go to **Settings → Secrets and variables → Actions → Repository variables** and add:

| Variable Name | Value | Purpose |
|---------------|-------|---------|
| `GOOGLE_CLOUD_PROJECT` | `your-project-id` | GCP project ID |
| `GCP_REGION` | `us-central1` | Deployment region |
| `TEST_MODE` | `false` | Production mode (real operations) |
| `ALPACA_PAPER_TRADING` | `true` | Use paper trading API |
| `ENABLE_EXECUTION` | `true` | Enable bracket order execution |
| `ENABLE_EQUITIES` | `false` | Disable stock trading |
| `ENABLE_GCP_LOGGING` | `true` | Enable structured logging |
| `DISABLE_SECRET_MANAGER` | `false` | Use Secret Manager (production) |
| `DISCORD_CHANNEL_ID_CRYPTO` | `your-crypto-channel-id` | Channel ID for thread recovery (crypto) |
| `DISCORD_CHANNEL_ID_STOCK` | `your-stock-channel-id` | Channel ID for thread recovery (stocks) |

**Workflow Integration:**

These variables are used in `.github/workflows/deploy.yml`:

```yaml
- name: Deploy to Cloud Run Job
  run: |
    gcloud run jobs update crypto-signals-job \
      --image="${IMAGE_TAG}" \
      --region=${{ vars.GCP_REGION }} \
      --set-env-vars="GOOGLE_CLOUD_PROJECT=${{ vars.GOOGLE_CLOUD_PROJECT }},..." \
      ...
```

**CI/CD Workflow Features:**

The GitHub Actions workflow (`.github/workflows/deploy.yml`) includes production-grade safety features:

1. **Concurrency Control:** Only one deployment runs at a time to prevent race conditions
2. **Smoke Testing:** After deployment, executes `python -m crypto_signals.main --smoke-test` to verify:
   - Firestore connectivity
   - Configuration validity
   - Basic system health
3. **Auto-Rollback:** If smoke test fails, automatically reverts the Cloud Run job to the previous `latest` image
4. **Promote-on-Success:** The `latest` tag is only applied after smoke test passes, ensuring it always points to a verified stable release
5. **Bypass Logic:** Add `[skip-smoke]` to your commit message to skip smoke testing (useful for docs-only changes)
6. **Detailed Notifications:** Discord alerts include per-step status (\ud83d\udfe2 Passed / \ud83d\udd34 Failed / \u23ed\ufe0f Skipped)

---

## 7. Verification and Testing

### 7.1. Test Manual Execution

Execute the Cloud Run job manually to verify deployment:

```bash
# Execute job and wait for completion
gcloud run jobs execute crypto-signals-job \
    --region=us-central1 \
    --wait

# Check execution status
gcloud run jobs executions list \
    --job=crypto-signals-job \
    --region=us-central1 \
    --limit=5
```

**Expected output:**
```
EXECUTION                              REGION        CREATION_TIME          DURATION  SUCCEEDED
crypto-signals-job-abc123              us-central1   2025-12-26 00:01:00    45s       1/1
```

---

### 7.2. Test Scheduler

Manually trigger the scheduler to verify configuration:

```bash
# Trigger scheduler
gcloud scheduler jobs run crypto-signals-daily --location=us-central1

# Wait 1-2 minutes, then check Cloud Run executions
gcloud run jobs executions list \
    --job=crypto-signals-job \
    --region=us-central1 \
    --limit=1
```

---

### 7.3. Verify Firestore Data

Check that signals are being stored in Firestore:

**Via Console:**
1. Go to [Firestore Console](https://console.cloud.google.com/firestore)
2. Navigate to `live_signals` collection
3. Verify documents are present with expected fields

**Via gcloud:**

```bash
# Query Firestore (requires firestore CLI setup)
gcloud firestore documents list live_signals --limit=5
```

---

### 7.4. Check Discord Notifications

Verify Discord notifications are working:

1. Check your test Discord channel for signal notifications
2. If using live mode, check crypto/stock channels
3. Verify threaded messages (updates appear in same thread)

**Test Discord Locally:**

```bash
poetry run python scripts/visual_discord_test.py success
```

---

## 8. Production Deployment Checklist

Use this checklist to verify complete deployment:

- [ ] **GCP Infrastructure**
  - [ ] All required APIs enabled
  - [ ] Artifact Registry repository created
  - [ ] Firestore initialized in Native Mode
  - [ ] BigQuery dataset created

- [ ] **Service Account**
  - [ ] Custom service account created (or using default)
  - [ ] All required IAM permissions granted
  - [ ] Service account JSON key created for GitHub

- [ ] **Secret Manager**
  - [ ] All secrets created (ALPACA_API_KEY, etc.)
  - [ ] No trailing newlines in secret values
  - [ ] Service account granted `secretAccessor` role on all secrets

- [ ] **Cloud Run Job**
  - [ ] Initial placeholder job created
  - [ ] Production image deployed
  - [ ] `GOOGLE_CLOUD_PROJECT` environment variable set
  - [ ] All other environment variables configured
  - [ ] All secrets mounted correctly
  - [ ] Manual execution successful

- [ ] **Cloud Scheduler**
  - [ ] Scheduler job created for 00:01 UTC
  - [ ] Correct URI format used
  - [ ] Service account configured for OAuth
  - [ ] Manual trigger test successful
  - [ ] Next run time verified

- [ ] **GitHub Configuration**
  - [ ] `GOOGLE_APPLICATION_CREDENTIALS` secret set
  - [ ] `GAR_REPOSITORY` secret set (correct format)
  - [ ] `DISCORD_DEPLOYS` secret set
  - [ ] All other secrets configured
  - [ ] All variables configured
  - [ ] GitHub Actions workflow runs successfully

- [ ] **Verification**
  - [ ] Manual job execution completes successfully
  - [ ] Scheduler triggers job correctly
  - [ ] Firestore data populated
  - [ ] Discord notifications received
  - [ ] Logs visible in Cloud Logging
  - [ ] No errors in execution logs

---

## Troubleshooting

For detailed troubleshooting of common errors:

- **Permission denied on secret** → [Error 1](./troubleshooting.md#error-1-permission-denied-on-secret)
- **Missing GOOGLE_CLOUD_PROJECT** → [Error 2](./troubleshooting.md#error-2-missing-google_cloud_project)
- **Boolean parsing error** → [Error 3](./troubleshooting.md#error-3-boolean-parsing-error)
- **Missing Docker image name** → [Error 4](./troubleshooting.md#error-4-missing-docker-image-name)
- **Invalid scheduler URI** → [Error 5](./troubleshooting.md#error-5-invalid-scheduler-uri)

**Quick Debugging Commands:**

```bash
# View recent job logs
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=crypto-signals-job" --limit=50

# Check job configuration
gcloud run jobs describe crypto-signals-job --region=us-central1

# Verify secret permissions
gcloud secrets get-iam-policy ALPACA_API_KEY

# Test scheduler
gcloud scheduler jobs run crypto-signals-daily --location=us-central1
```

See the complete [Troubleshooting Guide](./troubleshooting.md) for more details.

---

## Related Documentation

- [Troubleshooting Guide](./troubleshooting.md) - Common errors and solutions
- [Quick Start Deployment](../DEPLOYMENT.md) - Fast-track deployment for experienced users
- [Position Management](./position-management.md) - Trading execution details
- [Discord Threading](./discord-threading.md) - Notification system details

---

**Production Deployment History:**
- ✅ **December 26, 2025** - Production deployment validated
- Service account: `crypto-bot-admin@crypto-signal-bot-481500.iam.gserviceaccount.com`
- Cloud Scheduler: Daily execution at 00:01 UTC
- All troubleshooting scenarios documented from real production errors
