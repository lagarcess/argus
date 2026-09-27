#!/usr/bin/env bash
# Remove only the argus-native-auth-proof containers and volumes.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
native_auth_supabase stop --no-backup
docker volume ls --format '{{.Name}}' | grep 'argus-native-auth-proof' && {
  echo "leftover volumes above" >&2; exit 1; } || echo "no argus-native-auth-proof volumes remain"
