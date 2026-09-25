#!/bin/bash
# Classify whether every changed file is under docs/.
# Root-level *.md is not docs-only: backend tests read AGENTS.md and other
# root markdown. Non-pull_request events always run heavy jobs.

set -euo pipefail

write_result() {
  local docs_only="$1"
  local run_heavy="$2"
  printf 'docs_only=%s\n' "$docs_only"
  printf 'run_heavy=%s\n' "$run_heavy"
  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    {
      printf 'docs_only=%s\n' "$docs_only"
      printf 'run_heavy=%s\n' "$run_heavy"
    } >> "$GITHUB_OUTPUT"
  fi
}

is_docs_path() {
  local path="${1#./}"
  [ -n "$path" ] || return 1
  [ "$path" = "docs" ] || [ "${path#docs/}" != "$path" ]
}

classify_files() {
  local path
  if [ "$#" -eq 0 ]; then
    echo "No changed files given; fail closed to run_heavy=true."
    write_result "false" "true"
    return
  fi
  echo "Changed files:"
  for path in "$@"; do
    printf '  %s\n' "$path"
  done
  for path in "$@"; do
    if ! is_docs_path "$path"; then
      write_result "false" "true"
      return
    fi
  done
  write_result "true" "false"
}

collect_git_files() {
  local base_ref="$1"
  if ! git cat-file -e "${base_ref}^{commit}" 2>/dev/null; then
    git fetch --no-tags --depth=1 origin "$base_ref" >/dev/null
  fi
  git diff --name-only --no-renames --diff-filter=ACDMRTUXB "${base_ref}...HEAD"
}

MODE=""
FROM_GIT=""
FILES=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --files)
      MODE="files"
      shift
      FILES=("$@")
      break
      ;;
    --from-git)
      MODE="from-git"
      FROM_GIT="${2:-}"
      if [ -z "$FROM_GIT" ]; then
        echo "--from-git requires a base ref or SHA." >&2
        exit 2
      fi
      shift 2
      ;;
    -h|--help)
      cat <<'USAGE'
Usage:
  .github/docs-only-changes.sh --files path [path ...]
  .github/docs-only-changes.sh --from-git <base-ref-or-sha>

On pull_request CI, omit flags and set PR_BASE_SHA. Other events run heavy jobs.
USAGE
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [ "$MODE" = "files" ]; then
  classify_files "${FILES[@]+"${FILES[@]}"}"
  exit 0
fi

if [ "$MODE" = "from-git" ]; then
  mapfile -t FILES < <(collect_git_files "$FROM_GIT")
  classify_files "${FILES[@]+"${FILES[@]}"}"
  exit 0
fi

if [ "${GITHUB_EVENT_NAME:-}" != "pull_request" ]; then
  echo "Event '${GITHUB_EVENT_NAME:-local}' is not pull_request; run_heavy=true."
  write_result "false" "true"
  exit 0
fi

if [ -z "${PR_BASE_SHA:-}" ]; then
  echo "PR_BASE_SHA is required for pull_request classification; fail closed." >&2
  write_result "false" "true"
  exit 0
fi

mapfile -t FILES < <(collect_git_files "$PR_BASE_SHA")
classify_files "${FILES[@]+"${FILES[@]}"}"
