#!/bin/bash
# api.sh start [off] | kill9 | stop | wait
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY=/Users/garces/Documents/projects/repos/argus-worktrees/private-alpha-next/.venv/bin/python
case "$1" in
  start)
    flag=0; [ "${2:-}" = off ] && flag=1
    cd "$HERE"
    env -i PATH=/usr/bin:/bin HOME="$HOME" TMPDIR="${TMPDIR:-/tmp}" ISO_FLAG_OFF=$flag \
      nohup "$PY" "$HERE/launcher.py" >>"$HERE/api.log" 2>&1 &
    echo $! >"$HERE/api.pid"
    for i in $(seq 1 90); do
      curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8621/health 2>/dev/null | grep -q 200 && { echo "api up pid $(cat "$HERE/api.pid")"; exit 0; }
      sleep 1
    done
    echo "api did not come up"; tail -20 "$HERE/api.log"; exit 1;;
  kill9) kill -9 "$(cat "$HERE/api.pid")" && echo "killed -9 $(cat "$HERE/api.pid")";;
  stop) kill "$(cat "$HERE/api.pid")" 2>/dev/null; sleep 2; kill -9 "$(cat "$HERE/api.pid")" 2>/dev/null; echo stopped;;
esac
