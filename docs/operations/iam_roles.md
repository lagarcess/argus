# IAM Roles & Permissions Reference

**Last Updated:** 2026-02-02
**Context:** Service Account Permissions for `crypto-signals` (Deployment & Runtime).

This document outlines the Principle of Least Privilege (PoLP) configuration required for the Google Cloud Service Account used by GitHub Actions (CI/CD) and Cloud Run (Runtime).

## ✅ Verified Role List

Ensure the Service Account used in GitHub Secrets (`GOOGLE_APPLICATION_CREDENTIALS`) has the following roles:

| Role Name | GCP Role ID | Purpose |
| :--- | :--- | :--- |
| **Artifact Registry Writer** | `roles/artifactregistry.writer` | **Required for CI/CD**. Allows GitHub Actions to push Docker images to the registry. |
| **BigQuery Data Editor** | `roles/bigquery.dataEditor` | Allows creating/modifying tables (Schema Management) and reading/writing data. |
| **BigQuery Job User** | `roles/bigquery.jobUser` | Allows running query jobs (INSERT, UPDATE, MERGE). |
| **Cloud Datastore User** | `roles/datastore.user` | Read/Write access to Firestore (Strategy Config & Signals). |
| **Cloud Run Admin** | `roles/run.admin` | **Required for CI/CD**. Allows deploying and updating Cloud Run Jobs/Services. |
| **Cloud Run Invoker** | `roles/run.invoker` | Allows invoking the service (if not public) or checking status. |
| **Logging Admin** | `roles/logging.admin` | Allows writing structured logs to Cloud Logging. *(Note: `Log Writer` is sufficient, but Admin is acceptable).* |
| **Monitoring Editor** | `roles/monitoring.editor` | Allows writing custom metrics (if enabled). |
| **Secret Manager Secret Accessor** | `roles/secretmanager.secretAccessor` | **Critical**. Allows Cloud Run to read `.env` secrets (API Keys) at startup. |
| **Service Account User** | `roles/iam.serviceAccountUser` | **Required for CI/CD**. Allows the deployment process to "act as" the runtime service account when launching Cloud Run. |

## 🔍 Role Breakdown by Component

### 1. CI/CD (GitHub Actions)
These permissions are used during the **Build & Deploy** phase:
*   `Artifact Registry Writer`: Push the new image.
*   `Cloud Run Admin`: Update the Job definition.
*   `Service Account User`:Authorize the new Job to run as this identity.

### 2. Runtime (Cloud Run Instance)
These permissions are used by the **Running Application**:
*   `Secret Manager Secret Accessor`: Fetch `ALPACA_API_KEY`, Webhooks, etc.
*   `BigQuery Data Editor` + `Job User`: Run ETL pipelines.
*   `Cloud Datastore User`: access `dim_strategies`.
*   `Logging Admin`: Send telemetry.

## ⚠️ Troubleshooting

**Error: "Permission denied on secret"**
*   **Fix:** Check `Secret Manager Secret Accessor`. Ensure it is applied to the *Runtime* Service Account.

**Error: "403 Forbidden" during `docker push`**
*   **Fix:** Missing `Artifact Registry Writer`.

**Error: "Caller does not have permission 'iam.serviceAccounts.actAs'"**
*   **Fix:** Missing `Service Account User`. This is often overlooked but required for deployment agents.
