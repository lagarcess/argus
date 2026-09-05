# Real Postgres preview query proof

Captured 2026-09-05 UTC from the working tree based on
`93f3ee4c2b26ad4d0204b20f70ba1bc9c2a4f5c8`. The proof ran the actual
`PostgresKeysetReader.read_conversation_preview_messages` implementation against
Postgres 17.10 in an isolated local container. No hosted DSN, existing local
Supabase database, or real user data was used.

The [reusable harness](preview_sql_proof.py) uses a fixed loopback DSN restricted
to port 55431 and database `argus_531_preview_proof`, creates fresh minimal
tables, and seeds seven conversations and 24,010 synthetic messages. It uses
the production index `idx_messages_conversation_created` from
`20260424000001_alpha_core.sql`; it does not force planner settings or add a
test-only covering index.

The [captured result](preview-sql-proof.json) confirms one query and one pool
acquisition for six distinct requested conversations. Five owned conversations
were returned, while the foreign and unrequested conversations were excluded.
It proves timestamp/id tie ordering, cross-owner message exclusion, empty-chat
handling, both legacy marker exclusions, and unavailable previews for internal
system/tool content. The real query plan uses the production message index,
with five index-scan loops, an average one returned row per loop, and 25 shared
block hits. The seven-row conversation table uses a sequential scan, as expected
for this small fixture. Observed execution time was 0.08 ms; this is local query
evidence, not a hosted latency guarantee.

Source Git blob fingerprints observed after the run:

| Source | Blob |
| --- | --- |
| `src/argus/domain/postgres_keyset_reader.py` | `81314ca594f4f3be2da0e23416c4d300ad27c282` |
| `src/argus/domain/conversation_previews.py` | `ea070f9468519bd52783a6e3397e99cc7a1b616a` |
| `src/argus/api/conversation_previews.py` | `fb610d52fb58c76c4860182a52c7727c8f9175be` |
| `preview_sql_proof.py` | `bc005f24749a69b91e9de38c22f10929396607d3` |

The harness was formatted after execution; its behavior and the production
reader/query sources were unchanged. Review regression tests first failed for
both internal roles and a failed batch read, then passed after the bounded
unavailable projections were added. The final focused backend command passed
92 tests:

```sh
poetry run pytest tests/test_conversation_previews.py tests/test_postgres_keyset_reader.py tests/test_history_bounded_reads.py tests/test_search_bounded_reads.py --no-cov -q --tb=line
```

To reproduce, first confirm the container name and loopback port are unused,
then create a fresh disposable container:

```sh
docker run --detach --name argus-531-preview-proof --pull=never --publish 127.0.0.1:55431:5432 --env POSTGRES_HOST_AUTH_METHOD=trust --env POSTGRES_DB=argus_531_preview_proof postgres:17-alpine
poetry run python docs/reports/evidence/531/preview_sql_proof.py
docker stop argus-531-preview-proof
docker rm --volumes argus-531-preview-proof
```

Cleanup was verified: the exact proof container and its synthetic anonymous
database volume were removed, and port 55431 had no listener. Existing
`supabase_*_argus-qa` containers were left untouched. The retained evidence files
contain synthetic counts and plan structure only.
