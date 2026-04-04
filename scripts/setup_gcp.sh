#!/bin/bash
# =============================================================================
# GCP Resource Setup Script for Crypto Sentinel
# =============================================================================
# This script automates the GCP setup steps from DEPLOYMENT.md
# Usage: ./scripts/setup_gcp.sh <PROJECT_ID>
# =============================================================================

set -e

PROJECT_ID="${1:?Usage: $0 <PROJECT_ID>}"
REGION="${2:-us-central1}"

echo "🚀 Setting up GCP resources for Crypto Sentinel"
echo "   Project: $PROJECT_ID"
echo "   Region:  $REGION"
echo ""

# Set project
echo "📦 Configuring gcloud project..."
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo "📦 Enabling required APIs..."
gcloud services enable \
    run.googleapis.com \
    secretmanager.googleapis.com \
    firestore.googleapis.com \
    cloudscheduler.googleapis.com \
    artifactregistry.googleapis.com \
    logging.googleapis.com \
    bigquery.googleapis.com

echo "✅ APIs enabled"

# Create Artifact Registry repository
echo ""
echo "🗄️ Creating Artifact Registry repository..."
if gcloud artifacts repositories describe crypto-signals --location="$REGION"; then
    echo "   Repository already exists"
else
    echo "   Repository not found, creating..."
    gcloud artifacts repositories create crypto-signals \
        --repository-format=docker \
        --location="$REGION" \
        --description="Crypto Sentinel Docker images"
    echo "   Repository created"
fi

# Create Firestore database
echo ""
echo "📊 Creating Firestore database..."
if gcloud firestore databases describe; then
    echo "   Firestore database already exists"
else
    echo "   Firestore database not found, creating..."
    gcloud firestore databases create --region="$REGION"
    echo "   Firestore database created"
fi

# Summary and next steps
echo ""
echo "=============================================="
echo "✅ GCP Setup Complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Create secrets in Secret Manager:"
echo "   echo -n 'your-api-key' | gcloud secrets create ALPACA_API_KEY --data-file=-"
echo "   echo -n 'your-secret' | gcloud secrets create ALPACA_SECRET_KEY --data-file=-"
echo "   echo -n 'your-webhook' | gcloud secrets create TEST_DISCORD_WEBHOOK --data-file=-"
echo "   echo -n '$PROJECT_ID' | gcloud secrets create GOOGLE_CLOUD_PROJECT --data-file=-"
echo "   echo -n 'true' | gcloud secrets create ALPACA_PAPER_TRADING --data-file=-"
echo "   echo -n 'true' | gcloud secrets create TEST_MODE --data-file=-"
echo ""
echo "2. Create Cloud Run Job (see DEPLOYMENT.md section 3)"
echo ""
echo "3. Configure Cloud Scheduler (see DEPLOYMENT.md section 4)"
echo ""
echo "For full instructions, see: DEPLOYMENT.md"
