---
description: Catches 90% of failures locally before the push (Docker + GCP + Config)
---

1.  **Environment Check**
    - Verify GCP Authentication: `gcloud auth list`
    - Verify Project ID: `gcloud config get-value project`
    - Check for required `.env` variables (e.g., `GOOGLE_CLOUD_PROJECT`, `ALPACA_API_KEY`).

2.  **Container Verification**
    - Build production image: `docker build -t crypto-signals:preflight .`
    - Run local smoke test in container:
      ```bash
      docker run --rm -e DISABLE_SECRET_MANAGER=true -e ENVIRONMENT=DEV crypto-signals:preflight python -m crypto_signals.main --smoke-test
      ```
    - **Constraint**: If smoke test fails, do NOT proceed.

3.  **GCP Job Validation**
    - Verify target Cloud Run Job exists: `gcloud run jobs list --format="value(metadata.name)"`
    - Check for recent execution failures: `gcloud run jobs executions list --limit=5`

4.  **Reporting**
    - If all pass: "🟢 Pre-flight successful. Safe to run `/pr`."
    - If fail: Identify specifically if it's a **Build Error**, **Auth Error**, or **Smoke Test Error**.
