# GCP Deployment Guide: Crypto Sentinel

This guide documents the end-to-end process for deploying the Crypto Sentinel bot to Google Cloud Platform (GCP). It reflects the setup established for the `crypto-signals` project.

## 1. Prerequisites

*   A Google Cloud Platform Project with billing enabled.
*   Access to the Google Cloud Console or `gcloud` CLI (Cloud Shell recommended).
*   GitHub repository access with Admin permissions (to set Secrets/Variables).
*   Alpaca API Keys (Live or Paper).
*   Discord Webhook URLs (for notifications).

## 2. GCP Infrastructure Setup

You can perform these steps via the Google Cloud Console or using the `gcloud` CLI in Cloud Shell.

### 2.1. Enable Required APIs
Ensure the following APIs are enabled for your project:
*   `run.googleapis.com` (Cloud Run)
*   `secretmanager.googleapis.com` (Secret Manager)
*   `firestore.googleapis.com` (Firestore)
*   `cloudscheduler.googleapis.com` (Cloud Scheduler)
*   `artifactregistry.googleapis.com` (Artifact Registry)
*   `logging.googleapis.com` (Cloud Logging)
*   `bigquery.googleapis.com` (BigQuery)

**Command:**
```bash
gcloud services enable \
    run.googleapis.com \
    secretmanager.googleapis.com \
    firestore.googleapis.com \
    cloudscheduler.googleapis.com \
    artifactregistry.googleapis.com \
    logging.googleapis.com \
    bigquery.googleapis.com
```

### 2.2. Create Artifact Registry
Create a Docker repository to store your container images.

**Command:**
```bash
gcloud artifacts repositories create crypto-signals \
    --repository-format=docker \
    --location=us-central1 \
    --description="Crypto Sentinel Docker images"
```

### 2.3. Initialize Firestore
Ensure Firestore is provisioned in **Native Mode**.
*   Go to Firestore in GCP Console.
*   Click "Create Database".
*   Select "Native Mode".
*   Choose location (e.g., `nam5` / `us-central1`).

### 2.4. Create Secrets (Secret Manager)
The application requires several secrets to be stored in GCP Secret Manager.

**Command (Example):**
```bash
echo -n "YOUR_VALUE" | gcloud secrets create SECRET_NAME --data-file=-
```

**Required Secrets:**
1.  `ALPACA_API_KEY`: Your Alpaca API Key ID.
2.  `ALPACA_SECRET_KEY`: Your Alpaca Secret Key.
3.  `TEST_DISCORD_WEBHOOK`: Webhook URL for test/debug alerts.
4.  `LIVE_CRYPTO_DISCORD_WEBHOOK_URL`: Webhook URL for crypto signals.
5.  `LIVE_STOCK_DISCORD_WEBHOOK_URL`: Webhook URL for stock signals.

### 2.5. Grant Secret Manager Access to Cloud Run

The Cloud Run service account needs permission to access the secrets. By default, Cloud Run uses the Compute Engine default service account.

**Option A: Grant access to all secrets (recommended for simplicity)**
```bash
# Get your project number
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')

# Grant Secret Manager access to the default compute service account
gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

**Option B: Grant access per secret (more restrictive)**
```bash
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')

# Repeat for each secret
for SECRET in ALPACA_API_KEY ALPACA_SECRET_KEY TEST_DISCORD_WEBHOOK LIVE_CRYPTO_DISCORD_WEBHOOK_URL LIVE_STOCK_DISCORD_WEBHOOK_URL; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```

> **Note:** Without this step, Cloud Run will fail with "Permission denied on secret" errors.

## 3. GitHub Configuration

Configure your GitHub repository "Settings -> Secrets and variables -> Actions".

### 3.1. Repository Secrets
These are sensitive credentials used by the CI/CD pipeline.

| Secret Name | Value Description |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | The JSON key content of your Service Account (must have Editor/Cloud Run/Secret Access roles). |
| `GAR_REPOSITORY` | The full path to your Artifact Registry repo. Format: `us-central1-docker.pkg.dev/<PROJECT_ID>/crypto-signals` |
| `ALPACA_API_KEY` | Same as GCP secret (needed for CI tests). |
| `ALPACA_SECRET_KEY` | Same as GCP secret (needed for CI tests). |
| `TEST_DISCORD_WEBHOOK` | Same as GCP secret (needed for CI tests). |

### 3.2. Repository Variables
These are non-sensitive configuration flags managed centrally.

| Variable Name | Value | Description |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | `your-project-id` | The GCP Project ID (e.g., `crypto-signal-bot-481500`). |
| `GCP_REGION` | `us-central1` | The deployment region. |
| `TEST_MODE` | `false` | Set to `true` to dry-run logic, `false` for real persistence/ops. |
| `ALPACA_PAPER_TRADING` | `true` | Set to `true` for Paper API, `false` for Live API. |
| `ENABLE_EXECUTION` | `true` | Master switch for placing orders. |
| `ENABLE_GCP_LOGGING` | `true` | Enables structured JSON logging for Cloud Logging. |
| `DISABLE_SECRET_MANAGER` | `false` | Should usually be `false`. Set `true` only for local dev without GCP access. |

## 4. Initial Cloud Run Job Placeholder

The GitHub Actions workflow updates an *existing* Cloud Run Job. For the very first deployment, you must create a placeholder job so the "Update" command succeeds.

**Command (Cloud Shell):**
```bash
gcloud run jobs create crypto-signals-job \
    --region=us-central1 \
    --image=us-docker.pkg.dev/cloudrun/container/placeholder \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=your-project-id"
```

## 5. Deploying

1.  Push your changes to the `main` branch.
2.  Go to the **Actions** tab in GitHub.
3.  Watch the **Deploy** workflow.
    *   **CI Job**: Runs lint, security audit, and tests.
    *   **CD Job**: Builds Docker image, pushes to Artifact Registry, and updates the Cloud Run Job.

## 6. Verification

After a successful deployment:
1.  Go to **Cloud Run** in GCP Console.
2.  Select the `crypto-signals-job` job.
3.  Click **Execute** (or wait for Cloud Scheduler if configured) to manually trigger a run.
4.  Check the **Logs** tab to verify the bot is analyzing symbols and generating signals.
