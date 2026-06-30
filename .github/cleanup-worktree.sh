#!/usr/bin/env bash
# Remove generated dependency/build/test artifacts before deleting an Argus
# worktree. Safe mode keeps untracked source files and local env files intact.
set -euo pipefail

TARGET="${1:-$PWD}"
MODE="${2:-safe}"

cd "$TARGET"
ROOT="$(git rev-parse --show-toplevel)"
REMOTE="$(git remote get-url origin 2>/dev/null || true)"

case "$REMOTE" in
  *argus*) ;;
  *)
    echo "Refusing: this does not look like the Argus repo."
    exit 1
    ;;
esac

if [[ "$MODE" != "safe" && "$MODE" != "--wipe-untracked" ]]; then
  echo "Usage: .github/cleanup-worktree.sh [worktree-path] [--wipe-untracked]"
  exit 2
fi

echo "Cleaning worktree: $ROOT"
echo "Before:"
du -sh "$ROOT" 2>/dev/null || true

paths=(
  ".venv"
  "node_modules"
  "web/node_modules"
  ".pytest_cache"
  ".ruff_cache"
  ".mypy_cache"
  ".hypothesis"
  ".coverage"
  "coverage.xml"
  "htmlcov"
  "dist"
  "build"
  ".next"
  "web/.next"
  "web/out"
  "web/coverage"
  "web/playwright-report"
  "web/test-results"
  "playwright-report"
  "test-results"
  ".turbo"
  "temp"
)

for path in "${paths[@]}"; do
  if [[ -e "$ROOT/$path" ]]; then
    echo "Removing $path"
    rm -rf -- "$ROOT/$path"
  fi
done

find "$ROOT" \
  -path "$ROOT/.git" -prune -o \
  -type d -name "__pycache__" -print -exec rm -rf {} + 2>/dev/null || true

find "$ROOT" \
  -path "$ROOT/.git" -prune -o \
  -type f \( -name "*.pyc" -o -name "*.pyo" \) -print -delete 2>/dev/null || true

if [[ "$MODE" == "--wipe-untracked" ]]; then
  echo "Wiping ignored and untracked files because --wipe-untracked was passed."
  git clean -ffdx
else
  echo "Skipped git clean -ffdx."
  echo "Pass --wipe-untracked only when the worktree is disposable."
fi

echo "After:"
du -sh "$ROOT" 2>/dev/null || true

echo "Remaining git status:"
git status --short
