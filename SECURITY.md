# Security & Best Practices

## Overview

This document outlines security considerations, best practices, and operational guidelines for Crypto Sentinel in production environments.

## Security Architecture

### Threat Model

**Assets to Protect:**
1. API Credentials (Alpaca API keys)
2. Webhook URLs (Discord)
3. Trading positions and PnL data
4. Cloud infrastructure access

**Threat Vectors:**
1. Credential exposure via logs or code
2. Unauthorized access to cloud resources
3. API key compromise
4. Container escape vulnerabilities
5. Dependency vulnerabilities

## Secret Management

### Development Environment

**DO:**
- ✅ Use `.env` files (git-ignored)
- ✅ Set `DISABLE_SECRET_MANAGER=true`
- ✅ Use test mode for Discord (`TEST_MODE=true`)
- ✅ Use paper trading account (`ALPACA_PAPER_TRADING=true`)

**DON'T:**
- ❌ Commit `.env` files to git
- ❌ Share API keys via chat/email
- ❌ Use production credentials locally
- ❌ Log sensitive values

### Production Environment

**Mandatory:**
1. **Google Secret Manager**: All secrets must be in Secret Manager
2. **No .env files**: Secrets loaded at runtime from Secret Manager
3. **IAM Least Privilege**: Service account with minimal permissions
4. **Secret Rotation**: Rotate credentials every 90 days

**Setup:**
```bash
# Store secrets
gcloud secrets create ALPACA_API_KEY --data-file=-
gcloud secrets create ALPACA_SECRET_KEY --data-file=-
gcloud secrets create TEST_DISCORD_WEBHOOK --data-file=-

# Grant access to service account
gcloud secrets add-iam-policy-binding ALPACA_API_KEY \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor"
```

## API Security

### Alpaca API

**Best Practices:**
1. **Always use Paper Trading** in non-production environments
2. **Rate Limiting**: Default 0.5s delay between requests (max 200 req/min)
3. **Retry Logic**: Exponential backoff for failed requests (max 3 retries)
4. **API Key Rotation**: Rotate every 90 days
5. **Monitor Usage**: Track API usage in Alpaca dashboard

**Configuration:**
```python
ALPACA_PAPER_TRADING=true  # Paper trading only
RATE_LIMIT_DELAY=0.5       # Conservative rate limiting
```

**Rate Limit Formula:**
- Alpaca limit: 200 requests/minute
- Minimum delay: 60s / 200 = 0.3s per request
- Recommended: 0.5s (40% safety buffer)
- With 6 symbols: ~3 seconds total (well under limit)

### Discord Webhooks

**Best Practices:**
1. **Use Dedicated Webhook**: Create separate webhook for bot
2. **Test Mode**: Enable in development (`TEST_MODE=true`)
3. **Webhook Rotation**: Change webhook URL if compromised
4. **Content Validation**: Never include sensitive data in messages

**Security Risks:**
- ⚠️ Webhook URL in logs could leak to unauthorized users
- ⚠️ Anyone with webhook URL can post to channel
- ⚠️ No authentication on webhook endpoints

**Mitigation:**
```python
# BAD: Exposes webhook URL in code
client = DiscordClient()  # Old pattern without settings

# GOOD: Uses Settings for routing
client = DiscordClient(settings=settings)
```

## Container Security

### Dockerfile Best Practices

**Implemented:**
- ✅ Multi-stage build (reduces attack surface)
- ✅ Non-root user (`appuser`, UID 1000)
- ✅ Minimal base image (`python:3.11-slim`)
- ✅ No unnecessary tools in production image
- ✅ Explicit PYTHONPATH and PYTHONUNBUFFERED

**Security Layers:**
```dockerfile
# Stage 1: Build dependencies (discarded)
FROM python:3.11-slim as builder
RUN apt-get update && apt-get install -y build-essential git

# Stage 2: Runtime (minimal)
FROM python:3.11-slim
RUN useradd -m -u 1000 -s /bin/bash appuser  # Non-root
USER appuser  # Drop privileges
```

### Container Scanning

**Recommended Tools:**
1. **Trivy**: `trivy image crypto-signals:latest`
2. **Snyk**: `snyk container test crypto-signals:latest`
3. **Google Container Analysis**: Automatic in Artifact Registry

**Schedule:**
- Scan on every build (CI/CD)
- Weekly scans of production images
- Immediate action on CRITICAL vulnerabilities

## Cloud Security (GCP)

### IAM Permissions

**Service Account Minimal Permissions:**
```yaml
roles/secretmanager.secretAccessor  # Read secrets only
roles/datastore.user                # Firestore read/write
roles/bigquery.dataEditor           # BigQuery insert only
roles/logging.logWriter             # Cloud Logging
```

**Create Service Account:**
```bash
# Create account
gcloud iam service-accounts create crypto-signals \
    --description="Crypto Signals Bot" \
    --display-name="Crypto Signals"

# Grant minimal permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:crypto-signals@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:crypto-signals@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"
```

### Network Security

**Recommendations:**
1. **VPC Service Controls**: Restrict data exfiltration
2. **Private Google Access**: No public IPs for Cloud Run
3. **Egress Controls**: Allowlist only required domains
   - `*.alpaca.markets`
   - `discord.com`
   - `*.googleapis.com`

**Cloud Run Configuration:**
```bash
gcloud run jobs update crypto-signals-job \
    --vpc-connector=my-connector \
    --vpc-egress=private-ranges-only
```

### Data Protection

**Firestore:**
1. **Security Rules**: Deny public access
2. **TTL Policy**: 30-day retention for signals
3. **Backup Strategy**: Daily exports to Cloud Storage
4. **Encryption**: At-rest encryption enabled by default

**BigQuery:**
1. **Column-Level Security**: Mask PII fields
2. **Table Expiration**: 365 days for fact tables
3. **Audit Logs**: Track all queries
4. **Cost Controls**: Set per-project query limits

## Operational Security

### Logging

**Do Log:**
- ✅ Application events (signal generation, errors)
- ✅ API call success/failure (without credentials)
- ✅ Timing metrics and performance data
- ✅ User actions and system changes

**Don't Log:**
- ❌ API keys or secrets
- ❌ Full webhook URLs
- ❌ Passwords or tokens
- ❌ Sensitive PII

**Example:**
```python
# BAD
logger.info(f"Using API key: {api_key}")

# GOOD
logger.info("API authentication successful")
```

### Monitoring & Alerting

**Critical Alerts:**
1. **Failed Executions**: Job exit code != 0
2. **API Errors**: 3+ consecutive failures
3. **High Error Rate**: >10% failed operations
4. **Unusual Activity**: Unexpected API usage spike

**Setup:**
```bash
# Create alert policy
gcloud alpha monitoring policies create \
    --notification-channels=$CHANNEL_ID \
    --display-name="Crypto Signals Failures" \
    --condition-display-name="Job Failed" \
    --condition-threshold-value=1 \
    --condition-threshold-duration=60s
```

### Incident Response

**If Credentials Compromised:**

1. **Immediate Actions (< 5 minutes):**
   - Revoke compromised API keys
   - Disable Discord webhook
   - Stop all running jobs
   - Lock down cloud resources

2. **Investigation (< 1 hour):**
   - Review access logs
   - Check for unauthorized trades
   - Identify compromise source
   - Document timeline

3. **Recovery (< 4 hours):**
   - Generate new credentials
   - Update Secret Manager
   - Redeploy application
   - Verify functionality

4. **Post-Mortem (< 1 week):**
   - Root cause analysis
   - Implement preventive measures
   - Update runbooks
   - Team training

**Command Reference:**
```bash
# Emergency shutdown
gcloud run jobs delete crypto-signals-job --region=us-central1

# Revoke secret access
gcloud secrets delete ALPACA_API_KEY

# Check audit logs
gcloud logging read "protoPayload.authenticationInfo.principalEmail=$EMAIL" --limit=100
```

## Compliance & Auditing

### Audit Trail

**Required Logging:**
1. All API calls (timestamp, endpoint, result)
2. Secret access (who, when, which secret)
3. Configuration changes (before/after values)
4. Trade executions (entry/exit, PnL)

**Retention:**
- Application logs: 30 days
- Audit logs: 365 days
- Trade data: 7 years (regulatory requirement)

### Regular Reviews

**Weekly:**
- [ ] Check error rates in logs
- [ ] Review API usage patterns
- [ ] Monitor cloud costs

**Monthly:**
- [ ] Scan dependencies for vulnerabilities
- [ ] Review IAM permissions
- [ ] Test disaster recovery

**Quarterly:**
- [ ] Rotate API credentials
- [ ] Security audit of cloud resources
- [ ] Update dependencies

## Development Workflow

### Secure Development Practices

**Pre-commit Checks:**
1. **No Secrets**: Scan for hardcoded credentials
2. **Linting**: Flake8 for code quality
3. **Testing**: All tests pass
4. **Type Checking**: MyPy validation

**Tools:**
```bash
# Install pre-commit hooks
pre-commit install

# Scan for secrets
poetry add --dev detect-secrets
detect-secrets scan

# Security audit
poetry add --dev safety
safety check
```

### Code Review Checklist

- [ ] No hardcoded secrets
- [ ] Error handling for all external calls
- [ ] Structured logging with context
- [ ] Rate limiting on API calls
- [ ] Input validation on user data
- [ ] Graceful degradation on failures
- [ ] Tests for security-critical code

## Third-Party Dependencies

### Vulnerability Management

**Process:**
1. **Monitor**: GitHub Dependabot alerts
2. **Assess**: Review CVE severity and exploitability
3. **Patch**: Update vulnerable packages
4. **Test**: Verify no regressions
5. **Deploy**: Roll out updates

**Tools:**
```bash
# Check for outdated packages
poetry show --outdated

# Security audit
poetry audit

# Update dependencies
poetry update
```

### Supply Chain Security

**Best Practices:**
1. **Pin Versions**: Use exact versions in `poetry.lock`
2. **Hash Checking**: Verify package integrity
3. **Private Registry**: Consider internal PyPI mirror
4. **Review Updates**: Don't blindly update dependencies

## Disaster Recovery

### Backup Strategy

**What to Backup:**
1. Firestore data (live_signals, live_positions)
2. BigQuery tables (fact_trades, snapshot_accounts)
3. Configuration (infrastructure-as-code)
4. Secrets (encrypted backup of Secret Manager)

**Backup Schedule:**
```bash
# Daily Firestore export
gcloud firestore export gs://$BUCKET/firestore-backups/$(date +%Y%m%d)

# BigQuery snapshot
bq cp --snapshot crypto_sentinel.fact_trades \
    crypto_sentinel.fact_trades_snapshot_$(date +%Y%m%d)
```

### Recovery Procedures

**Scenario 1: Data Corruption**
```bash
# Restore from backup
gcloud firestore import gs://$BUCKET/firestore-backups/20240115
```

**Scenario 2: Complete System Failure**
1. Redeploy infrastructure from IaC
2. Restore secrets from encrypted backup
3. Restore data from latest backup
4. Verify health checks
5. Resume normal operations

**Recovery Time Objectives (RTO):**
- Data corruption: < 1 hour
- Service outage: < 15 minutes
- Complete failure: < 4 hours

## Questions & Support

For security issues, please contact the repository maintainers through GitHub's private vulnerability reporting feature.

For general questions: Open a GitHub issue with `[SECURITY]` prefix
