#!/usr/bin/env bash
# Runs every question in questions.json through a local Argus API served from
# D10_TREE, one conversation each, and writes <out_dir>/<id>.json. Paid: real
# interpreter and research provider calls. Usage:
#   D10_TREE=<tree> D10_ENV_FILE=<env> bash run_picture.sh <label> <out_dir>
set -euo pipefail
LABEL="$1"; OUT="$2"; HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$OUT"
export D10_API_PORT="${D10_API_PORT:-8610}" D10_TREE_LABEL="$LABEL"
poetry run python "$HERE/serve.py" > "$OUT/api.log" 2>&1 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 90); do
  curl -sf "http://127.0.0.1:$D10_API_PORT/api/v1/me" > /dev/null 2>&1 && break
  sleep 1
done
QUESTIONS="$(mktemp)"
python3 -c 'import json,sys
for row in json.load(open(sys.argv[1])):
    print("\t".join([row["id"], row["language"], row["question"]]))' "$HERE/questions.json" > "$QUESTIONS"
while IFS=$'\t' read -r id language question; do
  echo "== $id ($language)"
  poetry run python "$HERE/ask.py" "$id" "$language" "$question" "$OUT/$id.json" | head -40
done < "$QUESTIONS"
rm -f "$QUESTIONS"
kill $API_PID 2>/dev/null || true
wait $API_PID 2>/dev/null || true
