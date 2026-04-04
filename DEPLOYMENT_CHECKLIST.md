# Pre-Deployment Checklist

Use this checklist before deploying Crypto Sentinel to production.

## ✅ Prerequisites Setup

### Google Cloud Platform
- [ ] GCP project created
- [ ] Billing enabled
- [ ] gcloud CLI installed and authenticated
- [ ] Required APIs enabled:
  - [ ] Cloud Run API
  - [ ] Secret Manager API
  - [ ] Cloud Scheduler API
  - [ ] Firestore API
  - [ ] BigQuery API
  - [ ] Artifact Registry API
  - [ ] Cloud Logging API

### API Credentials
- [ ] Alpaca API key obtained
- [ ] Alpaca secret key obtained
- [ ] Discord webhook created
- [ ] All credentials documented securely

### Local Environment
- [ ] Python 3.9+ installed
- [ ] Poetry installed
- [ ] Docker installed
- [ ] Git configured

## ✅ Secret Manager Setup

- [ ] Created ALPACA_API_KEY secret
- [ ] Created ALPACA_SECRET_KEY secret
- [ ] Created TEST_DISCORD_WEBHOOK secret
- [ ] Created GOOGLE_CLOUD_PROJECT secret
- [ ] Created ALPACA_PAPER_TRADING secret
- [ ] Created TEST_MODE secret
- [ ] Created ENABLE_EQUITIES secret (default: false)
- [ ] Created ENABLE_EXECUTION secret (default: false)
- [ ] Created RISK_PER_TRADE secret (default: 100.0)
- [ ] (Optional) Created LIVE_CRYPTO_DISCORD_WEBHOOK_URL secret (for production)
- [ ] (Optional) Created LIVE_STOCK_DISCORD_WEBHOOK_URL secret (for production)
- [ ] Verified all secrets accessible via gcloud

## ✅ Local Testing

- [ ] Cloned repository
- [ ] Created `.env` file from `.env.example`
- [ ] Filled in all required credentials
- [ ] Ran `poetry install` successfully
- [ ] Ran health check: `poetry run python -m crypto_signals.scripts.health_check`
  - [ ] Alpaca Trading ✅
  - [ ] Alpaca Market Data ✅
  - [ ] Firestore ✅
  - [ ] BigQuery ✅
  - [ ] Discord ✅
- [ ] Ran main application: `poetry run python -m crypto_signals.main`
  - [ ] Processed all symbols
  - [ ] No errors
  - [ ] Signals saved to Firestore
  - [ ] Discord notifications sent (or mocked)

## ✅ Docker Testing

- [ ] Built Docker image: `docker build -t crypto-signals:latest .`
- [ ] Image built successfully (< 500MB)
- [ ] Ran with docker-compose: `docker-compose up`
- [ ] Container started successfully
- [ ] Application ran without errors
- [ ] Container stopped gracefully
- [ ] Ran health check container: `docker-compose --profile healthcheck run healthcheck`

## ✅ Firestore Configuration

- [ ] Firestore database created in us-central1 (or your region)
- [ ] Collection `live_signals` exists
- [ ] Collection `live_positions` exists (for execution engine)
- [ ] Test document created and read successfully
- [ ] Cleanup query tested (valid_until filter)
- [ ] TTL field verified on saved signals

## ✅ BigQuery Setup

- [ ] Dataset `crypto_sentinel` created
- [x] Tables created (Managed by Pipeline Engine):
  - [x] stg_trades_import (Auto-created on run)
  - [x] fact_trades (Auto-created on run)
  - [x] snapshot_accounts (Auto-created on run)
  - [ ] summary_strategy_performance
- [ ] Service account has BigQuery permissions

## ✅ Security Review

- [ ] No secrets in code
- [ ] No secrets in logs
- [ ] `.env` file in `.gitignore`
- [ ] Service account JSON not committed
- [ ] Reviewed SECURITY.md guidelines
- [ ] IAM permissions set to least privilege
- [ ] Rate limiting configured (RATE_LIMIT_DELAY >= 0.5)
- [ ] Paper trading enabled for initial deployment

## ✅ Execution Engine Verification (Optional)

> Only complete this section if enabling automated order execution.

### Risk Settings
- [ ] `RISK_PER_TRADE` set to appropriate value (default: $100)
- [ ] Risk per trade calculation verified: `qty = RISK_PER_TRADE / |entry - stop|`
- [ ] Position sizing tested with sample signals

### Safety Guards
- [ ] `ALPACA_PAPER_TRADING=true` confirmed (REQUIRED for execution)
- [ ] `ENABLE_EXECUTION=false` for initial deployment
- [ ] Understand dual safety requirement before enabling

### Alpaca Paper Trading
- [ ] Paper trading account funded (simulated balance)
- [ ] Paper trading API credentials verified
- [ ] Test order submitted manually via Alpaca dashboard
- [ ] Bracket order support confirmed for target symbols

### Firestore Position Collection
- [ ] `live_positions` collection created (auto on first save)
- [ ] Test position document verified structure:
  - `position_id` (matches `signal_id`)
  - `alpaca_order_id` (Alpaca's order ID)
  - `entry_fill_price`, `current_stop_loss`, `qty`, `side`
  - `status` (OPEN/CLOSED)

## ✅ Documentation Review

- [ ] Read README.md (architecture, setup)
- [ ] Read DEPLOYMENT.md (cloud deployment steps)
- [ ] Read SECURITY.md (security best practices)
- [ ] Read REVIEW_SUMMARY.md (review findings)
- [ ] Understand cost estimates (~$0.79/month initial)

## ✅ CI/CD Verification

- [ ] GitHub Actions pipeline succeeded on `main`
- [ ] Artifact pushed to Artifact Registry via workflow
- [ ] Cloud Run job image updated by workflow

## ✅ Cloud Deployment

### Artifact Registry
- [ ] Repository created: `crypto-signals`
- [ ] Docker configured for registry
- [ ] Image tagged correctly
- [ ] Image pushed successfully

### Cloud Run Job
- [ ] Job created: `crypto-signals-job`
- [ ] Secrets mapped correctly
- [ ] Resource limits set (1GB memory, 1 CPU)
- [ ] Service account assigned
- [ ] Timeout set appropriately (10 minutes)
- [ ] Test execution successful: `gcloud run jobs execute crypto-signals-job`

### Cloud Scheduler
- [ ] Main job scheduled: `crypto-signals-daily`
- [ ] Schedule configured (e.g., "0 9 * * *")
- [ ] Cleanup job scheduled: `crypto-signals-cleanup-daily`
- [ ] Schedule configured (e.g., "0 2 * * *")
- [ ] OAuth service account configured

### Cleanup Job
- [ ] Cleanup job created: `crypto-signals-cleanup`
- [ ] Command override set correctly
- [ ] Resource limits appropriate (512MB, 0.5 CPU)
- [ ] Test execution successful

## ✅ Monitoring Setup

- [ ] Cloud Logging configured
- [ ] Log filters created for errors
- [ ] Alerts configured for:
  - [ ] Job failures (exit code != 0)
  - [ ] Execution time > 5 minutes
  - [ ] Memory usage > 80%
  - [ ] Error rate > 10%
- [ ] Notification channels configured (email, SMS, etc.)

## ✅ Operational Readiness

- [ ] Runbook created for common issues
- [ ] On-call rotation defined (if applicable)
- [ ] Incident response procedures documented
- [ ] Backup strategy documented
- [ ] Rollback procedure tested
- [ ] Cost monitoring dashboard created
- [ ] Performance baseline established

## ✅ Phase 1: Staging (Week 1)

- [ ] Deployed to staging environment
- [ ] Ran daily for 7 days
- [ ] Monitored logs daily
- [ ] Verified cleanup job execution
- [ ] No critical errors observed
- [ ] Performance acceptable (< 30s execution)
- [ ] Costs within estimates

## ✅ Phase 2: Production (Week 2)

- [ ] Deployed to production environment
- [ ] Paper trading mode enabled
- [ ] Daily execution scheduled
- [ ] Monitoring alerts active
- [ ] Reviewed first week's logs
- [ ] Signals quality validated
- [ ] Discord notifications working
- [ ] Firestore data verified

## ✅ Phase 3: Scale (Month 2+)

- [ ] Increased to hourly execution (if desired)
- [ ] Expanded portfolio (if desired)
- [ ] Evaluated optimizations (#9-#12 in review)
- [ ] Considered live trading (if appropriate)

## 🎯 Final Verification

Before going live, verify these critical items:

### Critical Checks
- [ ] **All secrets in Secret Manager** (not in code or .env)
- [ ] **Paper trading enabled** (ALPACA_PAPER_TRADING=true)
- [ ] **Rate limiting configured** (RATE_LIMIT_DELAY >= 0.5)
- [ ] **Graceful shutdown tested** (SIGTERM handling works)
- [ ] **Cleanup job scheduled** (runs daily at 2 AM)
- [ ] **Monitoring alerts active** (receive test alert)
- [ ] **Rollback procedure documented** (know how to revert)
- [ ] **Emergency contacts defined** (who to call if down)

### Risk Assessment
- [ ] Reviewed residual risks in REVIEW_SUMMARY.md
- [ ] Mitigation strategies in place
- [ ] Acceptable risk level for organization

### Business Approval
- [ ] Stakeholders informed of deployment
- [ ] Budget approved (~$0.79/month initial)
- [ ] Maintenance schedule communicated
- [ ] Success metrics defined

## 📝 Sign-Off

**Deployed By:** _______________________
**Date:** _______________________
**Environment:** [ ] Staging  [ ] Production
**Version/Tag:** _______________________

**Approval:**
- [ ] Technical Lead: _______________________
- [ ] Security Team: _______________________
- [ ] Business Owner: _______________________

---

## 🆘 Emergency Contacts

**If Something Goes Wrong:**

1. **Check Logs:**
   ```bash
   gcloud logging tail "resource.type=cloud_run_job"
   ```

2. **Stop Job:**
   ```bash
   gcloud run jobs delete crypto-signals-job --region=us-central1
   ```

3. **Rollback:**
   ```bash
   gcloud run jobs update crypto-signals-job \
       --image=us-central1-docker.pkg.dev/$PROJECT/crypto-signals/crypto-signals:PREVIOUS_TAG
   ```

4. **Get Help:**
   - GitHub Issues: https://github.com/lagarcess/crypto-signals/issues
   - Documentation: See DEPLOYMENT.md, SECURITY.md

---

**Last Updated:** 2025-12-19
**Review Summary:** See REVIEW_SUMMARY.md for complete details
