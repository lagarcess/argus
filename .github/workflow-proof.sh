#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

run_python() {
  if [ -n "${ARGUS_WORKFLOW_PYTHON:-}" ]; then
    "$ARGUS_WORKFLOW_PYTHON" "$@"
    return
  fi

  poetry run python "$@"
}

usage() {
  cat <<'USAGE'
Usage:
  .github/workflow-proof.sh seed [--user-id <uuid>] [--conversation-id <uuid>] [--nonce <value>]
  .github/workflow-proof.sh local --job-id <uuid> --nonce <value>
  .github/workflow-proof.sh remote --job-id <uuid> --nonce <value>
  .github/workflow-proof.sh direct --job-id <uuid> --nonce <value>
  .github/workflow-proof.sh verify --job-id <uuid>

Seed creates a disposable proof auth/profile row when --user-id is omitted.
Use it only against a local or preview Supabase database for validation.

Local Render validation:
  1. poetry install --only workflows --no-root --no-interaction
  2. render workflows dev -- poetry run python workflows/main.py
  3. RENDER_USE_LOCAL_DEV=true .github/workflow-proof.sh local --job-id ... --nonce ...

This helper runs workflow Python entry points through `poetry run python` by default.
Set ARGUS_WORKFLOW_PYTHON=/path/to/python only when using a prebuilt workflow venv.

Remote validation requires:
  RENDER_API_KEY
  ARGUS_RENDER_WORKFLOW_PROOF_TASK={workflow-slug}/workflow_proof
  ARGUS_WORKFLOW_DATABASE_URL=<Supabase transaction pooler URL>

Future Render Workflow service settings:
  Root Directory: .
  Build Command: pip install poetry && poetry config virtualenvs.create false && poetry install --only workflows --no-root --no-interaction
  Start Command: poetry run python workflows/main.py

All modes that touch Supabase require ARGUS_WORKFLOW_DATABASE_URL as a secret.
DATABASE_URL is accepted only as a local/backward-compatible fallback.
USAGE
}

command="${1:-}"
if [ -z "$command" ]; then
  usage
  exit 2
fi
shift

case "$command" in
  seed)
    run_python workflows/proof.py seed "$@"
    ;;
  local)
    export RENDER_USE_LOCAL_DEV=true
    run_python workflows/trigger_proof.py "$@"
    ;;
  remote)
    run_python workflows/trigger_proof.py "$@"
    ;;
  direct)
    run_python workflows/proof.py direct "$@"
    ;;
  verify)
    run_python workflows/proof.py verify "$@"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage
    exit 2
    ;;
esac
