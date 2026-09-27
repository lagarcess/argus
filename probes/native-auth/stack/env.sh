# Sourced by the stack scripts. Every path is lane-owned and gitignored.
NATIVE_AUTH_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
NATIVE_AUTH_WORK="${NATIVE_AUTH_WORK:-$NATIVE_AUTH_ROOT/temp/native-auth-proof}"
NATIVE_AUTH_STACK_DIR="$NATIVE_AUTH_WORK/stack"
# A scratch HOME avoids the user's ~/.supabase/profile, which the CLI misreads.
NATIVE_AUTH_CLI_HOME="$NATIVE_AUTH_WORK/cli-home"
NATIVE_AUTH_API_PORT="${NATIVE_AUTH_API_PORT:-57460}"
NATIVE_AUTH_ADAPTER_PORT="${NATIVE_AUTH_ADAPTER_PORT:-57461}"
NATIVE_AUTH_EXCLUDE="vector,edge-runtime,imgproxy,studio,logflare,realtime,storage-api,postgres-meta,supavisor"
native_auth_supabase() {
  HOME="$NATIVE_AUTH_CLI_HOME" supabase "$@" --workdir "$NATIVE_AUTH_STACK_DIR"
}
