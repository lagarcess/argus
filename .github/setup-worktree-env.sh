#!/bin/bash
# Link missing local environment files from the canonical integration worktree.
set -euo pipefail

INTEGRATION_BRANCH="codex/private-alpha-next"
TARGET_ROOT="${1:-}"

warn() {
    echo "⚠️ [Setup] $*"
}

normalize_directory() {
    local directory="$1"
    (cd "$directory" 2>/dev/null && pwd -P)
}

find_integration_worktree() {
    local current_worktree=""
    local line=""

    while IFS= read -r line; do
        case "$line" in
            "worktree "*)
                current_worktree="${line#worktree }"
                ;;
            "branch refs/heads/$INTEGRATION_BRANCH")
                printf '%s\n' "$current_worktree"
                return 0
                ;;
        esac
    done < <(git -C "$TARGET_ROOT" worktree list --porcelain 2>/dev/null || true)

    return 1
}

link_environment_file() {
    local source="$1"
    local destination="$2"
    local label="$3"

    if [ -e "$destination" ] || [ -L "$destination" ]; then
        if [ -e "$source" ] && [ "$destination" -ef "$source" ]; then
            if [ -L "$destination" ]; then
                echo "🟢 [Setup] $label already links to the canonical worktree"
            else
                echo "🟢 [Setup] $label is the canonical worktree file"
            fi
        else
            warn "$label already exists; keeping it unchanged"
        fi
        return 0
    fi

    if [ ! -f "$source" ]; then
        warn "canonical $label is missing; no link was created"
        return 0
    fi

    mkdir -p "$(dirname "$destination")"
    ln -s "$source" "$destination"
    echo "🟢 [Setup] Linked $label from the canonical worktree"
}

if [ -z "$TARGET_ROOT" ]; then
    TARGET_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fi

if [ -z "$TARGET_ROOT" ] || ! TARGET_ROOT="$(normalize_directory "$TARGET_ROOT")"; then
    warn "target worktree was not found; environment files were not linked"
    exit 0
fi

CANONICAL_ROOT="${ARGUS_CANONICAL_WORKTREE_ROOT:-}"
if [ -z "$CANONICAL_ROOT" ]; then
    CANONICAL_ROOT="$(find_integration_worktree || true)"
fi

if [ -z "$CANONICAL_ROOT" ] || ! CANONICAL_ROOT="$(normalize_directory "$CANONICAL_ROOT")"; then
    warn "canonical integration worktree was not found; environment files were not linked"
    exit 0
fi

link_environment_file \
    "$CANONICAL_ROOT/.env" \
    "$TARGET_ROOT/.env" \
    "root .env"
link_environment_file \
    "$CANONICAL_ROOT/web/.env.local" \
    "$TARGET_ROOT/web/.env.local" \
    "web/.env.local"
