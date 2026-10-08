#!/bin/bash
# Positive control: Storage file runs while foreign_sweeper.py sweeps the same database on the real clock.
P=/private/tmp/claude-501/-Users-garces-Documents-projects-repos-argus--claude-worktrees-decision-attachment-refactor-098d43/a87878b8-b98a-412b-99b4-afda86e843b6/scratchpad/storage-proof
WT=/Users/garces/Documents/projects/repos/argus-worktrees/business-pilot-storage-proof
PY=/Users/garces/Documents/projects/repos/argus-worktrees/private-alpha-next/.venv/bin/python
set -a; . $P/stack/status.env; set +a
cd $WT
env -i HOME="$HOME" PATH="/usr/bin:/bin" PYTHONPATH=src:. PYTHONDONTWRITEBYTECODE=1 \
  ARGUS_DISPOSABLE_DATABASE_URL="$DB_URL" ARGUS_LOCAL_SUPABASE_URL="$API_URL" \
  ARGUS_LOCAL_SUPABASE_ANON_KEY="$ANON_KEY" ARGUS_LOCAL_SUPABASE_SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY" \
  "$PY" $P/foreign_sweeper.py 60 > $P/runs/control-sweeper.log 2>&1 &
SWEEPER=$!
sleep 2
{ echo "== control: Storage file x5 while a real-clock sweeper (pid $SWEEPER) sweeps the same database"
for i in 1 2 3 4 5; do
  $P/run.sh control-0$i tests/test_document_source_objects_postgres.py
  echo "control-0$i exit=$? | $(grep -E '^=+ .* in [0-9.]+s' $P/runs/control-0$i.log | tr -d '=') | $(grep -E '^(FAILED|ERROR) ' $P/runs/control-0$i.log | sed 's/ - .*//' | tr '\n' ' ')"
done
kill $SWEEPER 2>/dev/null; wait $SWEEPER 2>/dev/null
echo "sweeper stopped; still alive: $(ps -p $SWEEPER >/dev/null && echo yes || echo no)"; } > $P/control.log 2>&1
