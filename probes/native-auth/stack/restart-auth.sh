#!/usr/bin/env bash
# Switch captcha mode. The CLI applies auth config only on start, so this stops
# the stack while keeping its database volume, then starts it again.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
python3 "$(dirname "${BASH_SOURCE[0]}")/configure.py" "$NATIVE_AUTH_STACK_DIR" --captcha "${1:?mode}"
native_auth_supabase stop
native_auth_supabase start -x "$NATIVE_AUTH_EXCLUDE"
