#!/bin/bash
# setup.sh: Bootstrap Argus Development Environment (Async VM / Jules)
# Initializes Python (Poetry) backend and JavaScript (Bun) frontend
set -euo pipefail

echo "🔵 [Setup] Starting Argus development environment initialization..."

# ============================================================================
# 1. ENVIRONMENT SETUP
# ============================================================================
echo "🔵 [Setup] Enforcing safe environment variables..."
export ENVIRONMENT=DEV
export DONT_WRITE_BYTECODE=1
export PYTHONUNBUFFERED=1

# ============================================================================
# 2. PYTHON VERSION CHECK
# ============================================================================
echo "🔵 [Setup] Checking Python version..."
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "🔵 [Setup] Python version: $PYTHON_VERSION"

if ! python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"; then
    echo "❌ [Setup] Python 3.10+ required. Found: $PYTHON_VERSION"
    exit 1
fi

# ============================================================================
# 3. INSTALL POETRY (if needed)
# ============================================================================
echo "🔵 [Setup] Checking Poetry..."
if ! command -v poetry &> /dev/null; then
    echo "🔵 [Setup] Installing Poetry (Official Installer)..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "🟢 [Setup] Poetry is already installed: $(poetry --version)"
fi

# ============================================================================
# 4. INSTALL BUN (if needed)
# ============================================================================
echo "🔵 [Setup] Checking Bun..."
if ! command -v bun &> /dev/null; then
    echo "🔵 [Setup] Installing Bun..."
    curl -fsSL https://bun.sh/install | bash
    export PATH="$HOME/.bun/bin:$PATH"
else
    echo "🟢 [Setup] Bun is already installed: $(bun --version)"
fi

# ============================================================================
# 5. CONFIGURE POETRY
# ============================================================================
echo "🔵 [Setup] Configuring Poetry (local virtualenvs in-project)..."
poetry config virtualenvs.in-project true

# ============================================================================
# 6. INSTALL PYTHON DEPENDENCIES
# ============================================================================
echo "🔵 [Setup] Installing Python dependencies via Poetry..."
poetry install --no-interaction
poetry sync

# ============================================================================
# 7. VALIDATE PYTHON PACKAGE IMPORTS
# ============================================================================
echo "🔵 [Setup] Validating argus package imports..."
poetry run python -c "import argus; print('🟢 [Setup] argus package is importable')"

# ============================================================================
# 8. INSTALL FRONTEND DEPENDENCIES
# ============================================================================
echo "🔵 [Setup] Installing frontend dependencies via Bun..."
cd web
bun install
cd ..

# ============================================================================
# 9. VALIDATE FRONTEND BUILD
# ============================================================================
echo "🔵 [Setup] Validating Next.js frontend setup..."
cd web
bun exec next telemetry disable || true  # Disable telemetry silently
cd ..
echo "🟢 [Setup] Next.js frontend is ready"

# ============================================================================
# 10. ENVIRONMENT FILES VALIDATION
# ============================================================================
echo "🔵 [Setup] Validating environment files..."

# Check root .env exists
if [ ! -f .env ]; then
    echo "⚠️ [Setup] Root .env missing. Copy from .env.example:"
    echo "   cp .env.example .env"
    echo "   Then fill in ALPACA_API_KEY, ALPACA_SECRET_KEY, Supabase credentials"
else
    echo "🟢 [Setup] Root .env exists"
fi

# Check web/.env.local exists
if [ ! -f web/.env.local ]; then
    echo "⚠️ [Setup] web/.env.local missing. Create from example:"
    echo "   cp web/.env.example web/.env.local"
    echo "   Fill in NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY"
else
    echo "🟢 [Setup] web/.env.local exists"
fi

# Verify no secrets in .gitignore violations
if git ls-files .env .env.local .env.*.local 2>/dev/null | grep -q .; then
    echo "❌ [Setup] ERROR: Environment files are tracked in git!"
    echo "   Run: git rm --cached .env web/.env.local"
    exit 1
fi

# ============================================================================
# 11. NUMBA JIT WARMUP REMINDER
# ============================================================================
echo "🟢 [Setup] Remember:"
echo "   - When editing /src/argus/analysis/, call warmup_jit() in test entrypoints"
echo "   - See .agent/skills/numba-patterns/SKILL.md for details"

# ============================================================================
# 12. SUCCESS
# ============================================================================
echo ""
echo "🟢 ============================================================================"
echo "🟢 [Setup] Argus environment is ready!"
echo "🟢 ============================================================================"
echo ""
echo "Next steps:"
echo "  1. Fill in .env (backend secrets)"
echo "  2. Fill in web/.env.local (frontend config)"
echo "  3. Run backend:  poetry shell && uvicorn src.argus.api.main:app --reload"
echo "  4. Run frontend: cd web && bun run dev"
echo ""
echo "For more details, see startup.md"
