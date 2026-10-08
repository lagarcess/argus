#!/bin/bash
# usage: snapshot.sh <outfile>
OUT=$1; DB=supabase_db_argus-biz-storageproof
{
echo "# captured $(date -u +%Y-%m-%dT%H:%M:%SZ) on container $DB (host port 57792)"
echo "# required query"
docker exec $DB psql -U postgres -d postgres -c "select pid, client_addr, application_name, backend_start, state from pg_stat_activity where datname = 'postgres' order by backend_start"
echo "# same rows with user and query, to attribute each session"
docker exec $DB psql -U postgres -d postgres -c "select pid, usename, client_addr, application_name, backend_type, state, left(query, 70) as query from pg_stat_activity where datname = 'postgres' order by backend_start"
echo "# container addresses on the stack network (client_addr attribution)"
for c in $(docker ps --format '{{.Names}}' | grep argus-biz-storageproof); do echo "$c $(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{.Gateway}}{{end}}' $c)"; done
} > "$OUT" 2>&1
{
echo "# host processes with a TCP connection to the stack ports (57791 API, 57792 Postgres); listeners are Docker's port forwarders"
lsof -nP -iTCP:57791 -iTCP:57792 2>/dev/null || echo "(none)"
} >> "$OUT" 2>&1
