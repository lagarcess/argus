#!/usr/bin/env bash
# Start the lane-owned Supabase stack. Usage: up.sh [off|turnstile-pass|turnstile-fail]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
mkdir -p "$NATIVE_AUTH_CLI_HOME"
python3 "$(dirname "${BASH_SOURCE[0]}")/configure.py" "$NATIVE_AUTH_STACK_DIR" --captcha "${1:-off}"
native_auth_supabase start -x "$NATIVE_AUTH_EXCLUDE"
