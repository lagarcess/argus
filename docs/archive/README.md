# Documentation Archive

This directory contains historical versions of documentation files that have been superseded by newer versions.

## Purpose

Archived documents are kept for:
- Historical reference
- Understanding evolution of deployment processes
- Troubleshooting legacy deployments
- Migration guides

## Files

### GCP_DEPLOYMENT_GUIDE_V1.md
**Status:** Archived on December 26, 2025
**Replaced By:** `docs/GCP_DEPLOYMENT_GUIDE.md`

**Reason for Archive:**
The V1 guide was created before the actual production deployment and was missing several critical components that were discovered during real-world deployment:

- Cloud Scheduler configuration for daily 00:01 UTC execution
- `GOOGLE_CLOUD_PROJECT` environment variable requirement (caused ValidationError in production)
- Service account permission troubleshooting (Secret Manager access issues)
- `DISCORD_DEPLOYS` webhook for CI/CD notifications
- Comprehensive error handling documentation

The current guide (`docs/GCP_DEPLOYMENT_GUIDE.md`) reflects the validated production deployment process with all real-world errors and solutions documented.

## Note

⚠️ **Do not use archived documentation for new deployments.** Always refer to the current documentation in the main `docs/` directory.
