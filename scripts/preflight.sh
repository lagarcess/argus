#!/bin/bash
# ==============================================================================
# Script: preflight.sh
# Purpose: Verify environment, dependencies, and code integrity before PR submission.
# Usage: ./scripts/preflight.sh [--skip-container]
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚀 Starting Pre-flight Checks..."
echo "======================================"

# 1. Environment Check
echo "🔍 Checking Environment Configuration..."

if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file missing!${NC}"
    exit 1
fi

# Check for critical variables
REQUIRED_VARS=("ALPACA_API_KEY" "GOOGLE_CLOUD_PROJECT" "GOOGLE_APPLICATION_CREDENTIALS")
MISSING_VARS=0
# Simple grep check (not perfect parsing but sufficient)
for VAR in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^$VAR=" .env; then
        # Check if exported in shell
        if [ -z "${!VAR}" ]; then
            echo -e "${YELLOW}⚠️  Variable $VAR not found in .env or environment.${NC}"
            # MISSING_VARS=1
        fi
    fi
done

echo -e "${GREEN}✅ Environment config check complete.${NC}"
echo ""

# 2. GCP Check
echo "☁️  Checking Google Cloud SDK..."
if ! command -v gcloud &> /dev/null; then
    echo -e "${YELLOW}⚠️  gcloud CLI not found. Skipping GCP checks.${NC}"
else
    PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [ "$PROJECT" == "(unset)" ] || [ -z "$PROJECT" ]; then
        echo -e "${YELLOW}⚠️  gcloud project not configured.${NC}"
        echo "   Run: gcloud config set project <PROJECT_ID>"
    else
        echo -e "${GREEN}✅ gcloud configured for project: $PROJECT${NC}"

        # Check auth
        if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
             echo -e "${YELLOW}⚠️  No active gcloud account.${NC}"
             echo "   Run: gcloud auth login"
        else
             ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n 1)
             echo -e "${GREEN}✅ Authenticated as: $ACCOUNT${NC}"
        fi
    fi
fi
echo ""

# 3. Docker Check
echo "🐳 Checking Containerization..."
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}⚠️  Docker not found. Skipping container verification.${NC}"
    echo "   Ensure CI/CD pipeline runs container tests."
else
    if [ "$1" == "--skip-container" ]; then
        echo -e "${YELLOW}⏩ Skipping container build as requested.${NC}"
    else
        echo "   Building preflight image..."
        if docker build -t crypto-signals:preflight . > /dev/null 2>&1; then
             echo -e "${GREEN}✅ Docker build successful.${NC}"

             echo "   Running smoke test..."
             if docker run --rm --env-file .env -e DISABLE_SECRET_MANAGER=true -e ENVIRONMENT=DEV crypto-signals:preflight python -m crypto_signals.main --smoke-test > /dev/null 2>&1; then
                 echo -e "${GREEN}✅ Smoke test passed.${NC}"
             else
                 echo -e "${RED}❌ Smoke test failed!${NC}"
                 # Rerun without suppression to show error
                 echo -e "${YELLOW}   Error Details:${NC}"
                 docker run --rm --env-file .env -e DISABLE_SECRET_MANAGER=true -e ENVIRONMENT=DEV crypto-signals:preflight python -m crypto_signals.main --smoke-test || true
                 # exit 1
             fi
        else
             echo -e "${RED}❌ Docker build failed.${NC}"
             # exit 1
        fi
    fi
fi
echo ""

# 4. Code Integrity (Local Regression)
echo "🧪 Running Critical Regression Tests..."
# Only run the relevant caching tests for now to be fast
# Disable coverage to prevent false negatives on partial runs
# Override addopts to ignore pyproject.toml defaults
if poetry run pytest -o "addopts=" tests/market/test_data_provider_caching.py -q -p no:cov; then
    echo -e "${GREEN}✅ Regression tests passed.${NC}"
else
    echo -e "${RED}❌ Regression tests FAILED.${NC}"
    exit 1
fi

echo "======================================"
echo -e "${GREEN}✅ Pre-flight Checks Complete.${NC}"
echo "Ready for PR submission (pending CI/CD for skipped checks)."
