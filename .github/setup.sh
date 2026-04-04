#!/bin/bash
# setup.sh: Bootstrap the Argus Engine (Async VM / Jules Environment)
set -euo pipefail

echo "🔵 [Setup] Starting async VM environment initialization..."

# 1. Enforce Safe Environment Variables
echo "🔵 [Setup] Setting environment barriers..."
export ENVIRONMENT=DEV
export DONT_WRITE_BYTECODE=1

# 2. Check Python Version
echo "🔵 [Setup] Python version:"
python --version

# 3. Install Poetry (if not present)
if ! command -v poetry &> /dev/null; then
    echo "🔵 [Setup] Installing Poetry (Official Installer)..."
    curl -sSL https://install.python-poetry.org | python3 -
else
    echo "🟢 [Setup] Poetry is already installed."
fi

# 4. Configure Poetry (Local virtualenv strictly in project)
poetry config virtualenvs.in-project true

# 5. Install Dependencies (Non-interactive)
echo "🔵 [Setup] Installing dependencies via Poetry..."
poetry install --no-interaction --no-root

# 6. Validate Package Import
echo "🔵 [Setup] Validating argus package..."
poetry run python -c "import argus; print('🟢 [Setup] argus package importable')"

# 7. Core JIT Warmup Notification
echo "🟢 [Setup] Remember: When touching 'src/argus/analysis/', invoke 'warmup_jit()' in test entrypoints."

echo "🟢 [Setup] Async environment ready. Execute tickets."
