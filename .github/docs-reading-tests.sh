#!/bin/bash
# Print pytest-collectable files under tests/ that reference docs/.
# Matches both "docs/..." strings and Path("docs") / 'docs' components so a
# new doc-reading test joins without editing the workflow.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

is_collectable() {
  local name
  name="$(basename "$1")"
  case "$name" in
    test_*.py|*_test.py) return 0 ;;
    *) return 1 ;;
  esac
}

list_matches() {
  if command -v rg >/dev/null 2>&1; then
    rg -l --glob 'test_*.py' --glob '*_test.py' -e 'docs/' -e "['\"]docs['\"]" tests
    return
  fi
  git grep -l -e 'docs/' -e '"docs"' -e "'docs'" -- tests
}

while IFS= read -r path; do
  [ -n "$path" ] || continue
  if is_collectable "$path"; then
    printf '%s\n' "$path"
  fi
done < <(list_matches | sort -u)
