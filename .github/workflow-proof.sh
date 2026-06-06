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
  1. pip install -r workflows/requirements.txt
  2. render workflows dev -- python workflows/main.py
  3. RENDER_USE_LOCAL_DEV=true .github/workflow-proof.sh local --job-id ... --nonce ...

Remote validation requires:
  RENDER_API_KEY
  ARGUS_RENDER_WORKFLOW_PROOF_TASK={workflow-slug}/workflow_proof

All modes that touch Supabase require DATABASE_URL as a secret.
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
    python workflows/proof.py seed "$@"
    ;;
  local)
    export RENDER_USE_LOCAL_DEV=true
    python workflows/trigger_proof.py "$@"
    ;;
  remote)
    python workflows/trigger_proof.py "$@"
    ;;
  direct)
    python workflows/proof.py direct "$@"
    ;;
  verify)
    python workflows/proof.py verify "$@"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage
    exit 2
    ;;
esac
