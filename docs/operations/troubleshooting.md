# Troubleshooting Guide

**Last Updated:** December 27, 2025

This guide documents common errors encountered during deployment and operation of Crypto Sentinel on Google Cloud Platform, along with their solutions. All errors listed here were encountered and resolved in production.

## Table of Contents

- [Deployment Errors](#deployment-errors)
  - [Error 1: Permission Denied on Secret](#error-1-permission-denied-on-secret)
  - [Error 2: Missing GOOGLE_CLOUD_PROJECT](#error-2-missing-google_cloud_project)
  - [Error 3: Boolean Parsing Error](#error-3-boolean-parsing-error)
  - [Error 4: Missing Docker Image Name](#error-4-missing-docker-image-name)
  - [Error 5: Invalid Scheduler URI](#error-5-invalid-scheduler-uri)
  - [Error 6: Scheduler Status Code 5 (NOT_FOUND)](#error-6-scheduler-status-code-5-not_found)
- [Debugging Commands](#debugging-commands)
  - [View Cloud Run Logs](#view-cloud-run-logs)
  - [Check Scheduler Status](#check-scheduler-status)
  - [Verify Secret Permissions](#verify-secret-permissions)
  - [Test Cloud Run Job Manually](#test-cloud-run-job-manually)
- [Common Workflow Deployment Failures](#common-workflow-deployment-failures)

---

## Deployment Errors

### Error 1: Permission Denied on Secret

**Error Message:**
```
Permission denied on secret: projects/crypto-signal-bot-481500/secrets/ALPACA_API_KEY/versions/latest
```

**Cause:**
The Cloud Run service account does not have permission to access secrets stored in Google Secret Manager.

**Solution:**

Grant `roles/secretmanager.secretAccessor` to the service account used by Cloud Run:

```bash
# If using a custom service account (replace with your service account email)
gcloud secrets add-iam-policy-binding ALPACA_API_KEY \
  --member="serviceAccount:crypto-bot-admin@PROJECT-ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# If using the default compute service account
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding ALPACA_API_KEY \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**Grant access to all secrets at once:**

```bash
# Replace with your service account email
SERVICE_ACCOUNT="crypto-bot-admin@PROJECT-ID.iam.gserviceaccount.com"

for SECRET in ALPACA_API_KEY ALPACA_SECRET_KEY TEST_DISCORD_WEBHOOK LIVE_CRYPTO_DISCORD_WEBHOOK_URL LIVE_STOCK_DISCORD_WEBHOOK_URL; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
done
```

**Verification:**

```bash
# Check permissions on a secret
gcloud secrets get-iam-policy ALPACA_API_KEY

# You should see your service account listed with the secretAccessor role
```

---

### Error 2: Missing GOOGLE_CLOUD_PROJECT

**Error Message:**
```
ValidationError: 1 validation error for Settings
GOOGLE_CLOUD_PROJECT
  Field required [type=missing, input_value={...}, input_type=dict]
```

**Cause:**
The `GOOGLE_CLOUD_PROJECT` environment variable is required by Pydantic configuration but was not set in the Cloud Run job environment.

**Solution:**

Add `GOOGLE_CLOUD_PROJECT` to the Cloud Run job environment variables:

```bash
gcloud run jobs update crypto-signals-job \
  --region=us-central1 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=your-project-id"
```

**Or update via GitHub Actions workflow:**

Ensure your `.github/workflows/deploy.yml` includes `GOOGLE_CLOUD_PROJECT` in the `--set-env-vars` flag:

```yaml
- name: Deploy to Cloud Run Job
  run: |
    gcloud run jobs update crypto-signals-job \
      --image="${IMAGE_TAG}" \
      --region=${{ vars.GCP_REGION }} \
      --set-env-vars="GOOGLE_CLOUD_PROJECT=${{ vars.GOOGLE_CLOUD_PROJECT }},..." \
      ...
```

**Verification:**

```bash
# Check environment variables on the job
gcloud run jobs describe crypto-signals-job --region=us-central1 --format="value(spec.template.spec.containers[0].env)"
```

---

### Error 3: Boolean Parsing Error

**Error Message:**
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
ALPACA_PAPER_TRADING
  Input should be a valid boolean, unable to interpret input [type=bool_parsing, input_value='true\r\n', input_type=str]
```

**Cause:**
Environment variable values have trailing newline characters (`\r\n`) from copy-paste or improper secret creation.

**Solution:**

When creating secrets, use `echo -n` to prevent newline characters:

```bash
# CORRECT - no trailing newline
echo -n "true" | gcloud secrets create ALPACA_PAPER_TRADING --data-file=-

# INCORRECT - includes newline
echo "true" | gcloud secrets create ALPACA_PAPER_TRADING --data-file=-
```

**Fix existing secrets:**

```bash
# Update the secret with the correct value
echo -n "true" | gcloud secrets versions add ALPACA_PAPER_TRADING --data-file=-
```

**Verification:**

```bash
# Check the secret value (should not show newline)
gcloud secrets versions access latest --secret=ALPACA_PAPER_TRADING | od -c
```

---

### Error 4: Missing Docker Image Name

**Error Message:**
```
Error: name invalid: Missing image name
```

**Cause:**
The `GAR_REPOSITORY` GitHub secret is not set or is malformed, causing the Docker build/push to fail.

**Solution:**

Set the `GAR_REPOSITORY` secret in GitHub repository settings with the correct format:

1. Go to **Settings → Secrets and variables → Actions → Repository secrets**
2. Create or update `GAR_REPOSITORY` with value:
   ```
   us-central1-docker.pkg.dev/PROJECT-ID/crypto-signals/crypto-signals
   ```

**Format:**
```
{REGION}-docker.pkg.dev/{PROJECT-ID}/{REPOSITORY}/{IMAGE-NAME}
```

**Example:**
```
us-central1-docker.pkg.dev/crypto-signal-bot-481500/crypto-signals/crypto-signals
```

**Verification:**

Check that the secret is set in GitHub:
```bash
# In GitHub Actions logs, you should see:
# IMAGE_TAG=us-central1-docker.pkg.dev/PROJECT-ID/crypto-signals/crypto-signals:SHA
```

---

### Error 5: Invalid Scheduler URI

**Error Message:**
```
ERROR: (gcloud.scheduler.jobs.create.http) INVALID_ARGUMENT: Invalid url for HttpRequest.oauth_token
```

**Cause:**
The Cloud Scheduler URI format is incorrect. Must use the newer `run.googleapis.com` endpoint format instead of the regional endpoint format.

**Solution:**

Use the correct URI format for Cloud Scheduler:

```bash
# CORRECT - uses regional endpoint for v1 API
gcloud scheduler jobs create http crypto-signals-daily \
  --location=us-central1 \
  --schedule="1 0 * * *" \
  --time-zone="UTC" \
  --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT-ID/jobs/crypto-signals-job:run" \
  --http-method=POST \
  --oauth-service-account-email="SERVICE-ACCOUNT-EMAIL" \
  --description="Capture daily crypto candle closes at 00:01 UTC"

# INCORRECT - uses wrong endpoint format (will fail with status code 5)
# --uri="https://run.googleapis.com/v1/projects/PROJECT-ID/locations/us-central1/jobs/crypto-signals-job:run"
```

**Correct URI Format:**
```
https://{REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/{PROJECT-ID}/jobs/{JOB-NAME}:run
```

**Verification:**

```bash
# Check scheduler job configuration
gcloud scheduler jobs describe crypto-signals-daily --location=us-central1

# Test scheduler job
gcloud scheduler jobs run crypto-signals-daily --location=us-central1
```

---

### Error 6: Scheduler Status Code 5 (NOT_FOUND)

**Error Message:**
```
status:
  code: 5
```

**Symptoms:**
- Cloud Scheduler shows `status.code: 5` after `lastAttemptTime`
- No Cloud Run job execution is created when scheduler triggers
- Manual `gcloud scheduler jobs run` completes without error but job doesn't start

**Cause:**
Two possible causes:
1. The Cloud Scheduler URI format is incorrect (see [Error 5](#error-5-invalid-scheduler-uri))
2. The service account does not have `roles/run.invoker` on the Cloud Run **job** itself (project-level permissions are not sufficient)

**Solution:**

Grant `roles/run.invoker` on the Cloud Run job:

```bash
gcloud run jobs add-iam-policy-binding crypto-signals-job \
  --region=us-central1 \
  --member="serviceAccount:crypto-bot-admin@PROJECT-ID.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

**Verification:**


---

### Error 7: Firestore Index GRPC Error

**Error Message:**
```
grpc.StatusCode.FAILED_PRECONDITION: The query requires an index.
```

**Cause:**
Missing Composite Index for sector cap queries (`status` + `asset_class`) in `RiskEngine`.

**Solution:**
Create the index via CLI:
```bash
gcloud firestore indexes composite create \
    --collection-group=live_positions \
    --field-config field-path=status,order=ascending \
    --field-config field-path=asset_class,order=ascending
```

**How to distinguish manual vs scheduled runs:**

Look at the `RUN BY` column in executions list:
- **Manual run**: Shows your email (e.g., `user@gmail.com`)
- **Scheduled run**: Shows service account (e.g., `crypto-bot-admin@PROJECT.iam.gserviceaccount.com`)

---

## Debugging Commands

### View Cloud Run Logs

**View recent job execution logs:**

```bash
# View last 50 log entries
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=crypto-signals-job" \
  --limit=50 \
  --format=json

# Follow logs in real-time
gcloud logging tail "resource.type=cloud_run_job AND resource.labels.job_name=crypto-signals-job"

# View logs for a specific execution
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=crypto-signals-job AND timestamp>=\"2025-12-26T00:00:00Z\"" \
  --format=json

# Filter for errors only
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=crypto-signals-job AND severity>=ERROR" \
  --limit=50
```

**View logs in Cloud Console:**
1. Go to **Cloud Run → Jobs → crypto-signals-job**
2. Click on **Logs** tab
3. Select an execution to view its logs

---

### Check Scheduler Status

**List all scheduler jobs:**

```bash
gcloud scheduler jobs list --location=us-central1
```

**Describe specific scheduler job:**

```bash
gcloud scheduler jobs describe crypto-signals-daily --location=us-central1
```

**View scheduler execution history:**

```bash
# View recent scheduler logs
gcloud logging read "resource.type=cloud_scheduler_job AND resource.labels.job_name=crypto-signals-daily" \
  --limit=20 \
  --format=json
```

**Manually trigger scheduler:**

```bash
gcloud scheduler jobs run crypto-signals-daily --location=us-central1
```

**Pause/Resume scheduler:**

```bash
# Pause scheduler
gcloud scheduler jobs pause crypto-signals-daily --location=us-central1

# Resume scheduler
gcloud scheduler jobs resume crypto-signals-daily --location=us-central1
```

**Check next scheduled run:**

```bash
gcloud scheduler jobs describe crypto-signals-daily --location=us-central1 --format="value(schedule, timeZone, state)"
```

---

### Verify Secret Permissions

**Check IAM policy on a secret:**

```bash
gcloud secrets get-iam-policy ALPACA_API_KEY
```

**List all secrets and their versions:**

```bash
gcloud secrets list
gcloud secrets versions list ALPACA_API_KEY
```

**Test secret access from Cloud Run:**

```bash
# Execute a test job that prints the secret (CAREFUL - logs may expose secrets)
gcloud run jobs execute crypto-signals-job --region=us-central1
```

**Verify service account has access:**

```bash
# List all IAM bindings for a secret
gcloud secrets get-iam-policy ALPACA_API_KEY --format=json | jq '.bindings[] | select(.role=="roles/secretmanager.secretAccessor")'
```

**Batch verify all required secrets exist:**

```bash
for secret in ALPACA_API_KEY ALPACA_SECRET_KEY TEST_DISCORD_WEBHOOK \
  LIVE_CRYPTO_DISCORD_WEBHOOK_URL LIVE_STOCK_DISCORD_WEBHOOK_URL \
  DISCORD_SHADOW_WEBHOOK_URL DISCORD_BOT_TOKEN; do
    gcloud secrets describe $secret > /dev/null 2>&1 && \
    echo "✅ $secret exists" || echo "❌ $secret MISSING";
done
```

---

### Test Cloud Run Job Manually

**Execute job manually:**

```bash
# Execute job and wait for completion
gcloud run jobs execute crypto-signals-job --region=us-central1 --wait

# Execute job without waiting
gcloud run jobs execute crypto-signals-job --region=us-central1
```

**List recent job executions:**

```bash
gcloud run jobs executions list \
  --job=crypto-signals-job \
  --region=us-central1 \
  --limit=10
```

**Describe specific execution:**

```bash
# Get execution name from list command
gcloud run jobs executions describe EXECUTION-NAME \
  --region=us-central1
```

**Check job configuration:**

```bash
# View full job configuration
gcloud run jobs describe crypto-signals-job --region=us-central1

# View only environment variables
gcloud run jobs describe crypto-signals-job --region=us-central1 \
  --format="value(spec.template.spec.containers[0].env)"

# View only secrets configuration
gcloud run jobs describe crypto-signals-job --region=us-central1 \
  --format="value(spec.template.spec.containers[0].env[].valueFrom.secretKeyRef)"
```

---

## Common Workflow Deployment Failures

### CI Job Fails: Linting Errors

**Error:** `poetry run ruff check .` fails

**Solution:**
Fix linting errors locally before pushing:

```bash
# Check for linting errors
poetry run ruff check .

# Auto-fix linting errors
poetry run ruff check --fix .

# Format code
poetry run ruff format .
```

---

### CI Job Fails: Test Failures

**Error:** Tests fail during `poetry run pytest`

**Solution:**
Run tests locally to debug:

```bash
# Run all tests
poetry run pytest

# Run specific test
poetry run pytest tests/test_main.py -v

# Run with coverage
poetry run pytest --cov=src/crypto_signals --cov-report=term-missing
```

---

### CD Job Fails: Authentication Error

**Error:**
```
ERROR: (gcloud.auth.activate-service-account) The provided credentials are invalid
```

**Solution:**
Check that `GOOGLE_APPLICATION_CREDENTIALS` secret is correctly set:

1. Verify the secret contains valid JSON service account key
2. Ensure the service account has necessary permissions:
   - Cloud Run Admin
   - Artifact Registry Writer
   - Secret Manager Admin

```bash
# Test service account locally
gcloud auth activate-service-account --key-file=service-account-key.json
gcloud auth list
```

---

### CD Job Fails: Image Not Found

**Error:**
```
ERROR: (gcloud.run.jobs.update) Image 'us-central1-docker.pkg.dev/...' not found
```

**Cause:**
Docker image was not successfully pushed to Artifact Registry.

**Solution:**

1. Check Docker build logs in GitHub Actions
2. Verify Artifact Registry repository exists:
   ```bash
   gcloud artifacts repositories list --location=us-central1
   ```
3. Verify Docker authentication:
   ```bash
   gcloud auth configure-docker us-central1-docker.pkg.dev
   ```
4. Manually push image to test:
   ```bash
   docker build -t us-central1-docker.pkg.dev/PROJECT-ID/crypto-signals/crypto-signals:test .
   docker push us-central1-docker.pkg.dev/PROJECT-ID/crypto-signals/crypto-signals:test
   ```

---

### Deployment Succeeds but Job Fails at Runtime

**Symptoms:**
- GitHub Actions deployment succeeds (✅)
- Cloud Run job fails when executed (❌)

**Common Causes:**

1. **Missing environment variables**
   - Check job configuration: `gcloud run jobs describe crypto-signals-job --region=us-central1`
   - Verify `GOOGLE_CLOUD_PROJECT` is set

2. **Secret access issues**
   - Check service account permissions (see [Error 1](#error-1-permission-denied-on-secret))
   - Verify secrets exist: `gcloud secrets list`

3. **Code errors**
   - View execution logs: `gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=crypto-signals-job AND severity>=ERROR"`
   - Test code locally with same environment variables

4. **Resource limits**
   - Check if job is running out of memory or timing out
   - Increase limits if needed:
     ```bash
     gcloud run jobs update crypto-signals-job \
       --region=us-central1 \
       --memory=2Gi \
       --task-timeout=15m
     ```

---

## Getting Help

If you encounter an error not covered in this guide:

1. **Check Cloud Run logs** for detailed error messages
2. **Review GitHub Actions logs** for deployment failures
3. **Search Google Cloud documentation** for the specific error code
4. **Open an issue** on GitHub with:
   - Complete error message
   - Steps to reproduce
   - Relevant logs (redact secrets!)
   - Environment configuration

---

**Related Documentation:**
- [GCP Deployment Guide](./deployment-guide.md)
- [Quick Start Deployment](../DEPLOYMENT.md)
- [GitHub Workflows](../.github/workflows/deploy.yml)
