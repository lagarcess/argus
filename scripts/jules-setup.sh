#!/bin/bash
# jules-setup.sh: Automated environment setup for Jules (Agentic VM)
# This script ensures the VM is configured for testing and review without risking production data.

set -e

echo "🚀 Initializing environment for Jules..."

# 1. Environment Safety
# Strictly enforce DEV environment and disable execution to prevent accidental live trades.
export ENVIRONMENT=DEV
export ENABLE_EXECUTION=false
export TEST_MODE=true
export DISABLE_SECRET_MANAGER=true # Force local/mocked secrets if needed

if [ "$ENVIRONMENT" == "PROD" ]; then
    echo "❌ ERROR: ENVIRONMENT is set to PROD. This setup script is for review/test only."
    exit 1
fi

# 2. Dependency Installation
echo "📦 Installing dependencies via Poetry..."
poetry install

# 3. JIT Warmup
# Pre-compile Numba JIT functions to verify performance-critical paths.
echo "🔥 Performing JIT Warmup..."
poetry run python -c "from crypto_signals.analysis.structural import warmup_jit; warmup_jit(); print('✅ JIT Warmup Successful')"

# 4. Context Validation
# Check if AGENTS.md exists and is readable
if [ ! -f "AGENTS.md" ]; then
    echo "⚠️ WARNING: AGENTS.md not found in root. Jules might lack architectural context."
fi

echo "✨ Environment setup complete. Jules is ready for autonomous tasks."
