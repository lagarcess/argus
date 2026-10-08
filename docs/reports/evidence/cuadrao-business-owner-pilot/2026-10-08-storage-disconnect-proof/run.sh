#!/bin/bash
# usage: run.sh <label> <pytest targets...>   one fresh pytest process, junit + log under runs/
P=/private/tmp/claude-501/-Users-garces-Documents-projects-repos-argus--claude-worktrees-decision-attachment-refactor-098d43/a87878b8-b98a-412b-99b4-afda86e843b6/scratchpad/storage-proof
WT=/Users/garces/Documents/projects/repos/argus-worktrees/business-pilot-storage-proof
PY=/Users/garces/Documents/projects/repos/argus-worktrees/private-alpha-next/.venv/bin/python
LABEL=$1; shift
set -a; . $P/stack/status.env; set +a
cd $WT && exec env -i HOME="$HOME" PATH="/usr/bin:/bin:/usr/sbin:/sbin" LANG=en_US.UTF-8 \
  PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 \
  ARGUS_DISPOSABLE_DATABASE_URL="$DB_URL" \
  ARGUS_LOCAL_SUPABASE_URL="$API_URL" \
  ARGUS_LOCAL_SUPABASE_ANON_KEY="$ANON_KEY" \
  ARGUS_LOCAL_SUPABASE_SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY" \
  "$PY" -m pytest "$@" -p no:cacheprovider --no-cov -rA -q \
  --junitxml="$P/runs/$LABEL.xml" > "$P/runs/$LABEL.log" 2>&1
