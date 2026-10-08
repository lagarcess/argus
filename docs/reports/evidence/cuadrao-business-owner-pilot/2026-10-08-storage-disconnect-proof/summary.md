# Storage disconnect test: isolation proof

Worktree business-pilot-storage-proof, detached at integration 826ace6d4 (contains #924, cd3231baa). Dedicated local Supabase stack `argus-biz-storageproof` (API 57791, Postgres 57792, Studio 57793, mail 57794, shadow 57790, pooler 57799 disabled, analytics 57797 disabled). Config copied from spacestack with only project_id and ports changed. 119 migrations synced from the worktree, then `supabase db reset --local`. No provider keys in any process (env -i). No hosted calls.

## Results

| Set | Runs | Run result | test_disconnect_removes_the_object_and_keeps_confirmed_activity | test_disconnect_during_preparation_leaves_no_object_and_no_row |
|---|---|---|---|---|
| Storage file alone, fresh process per run | 20 | 20 x "19 passed" | 20/20 | 20/20 |
| Jobs file then Storage file, one process per run | 20 | 20 x "27 passed" | 20/20 | 20/20 |
| Positive control: Storage file alone while a separate real-clock sweeper process sweeps the same database | 5 | 3 x "1 failed, 18 passed", 2 x "19 passed" | 2/5 (3 failures) | 5/5 |

Every other test in both files passed 20/20 in both sets. In the combined set that includes `test_two_running_instances_recover_a_dead_worker_without_restart` (20/20). Per-run lines and tallies are in runs.log; the control's are in control.log. Each run's full log and JUnit XML is under runs/.

Before the 40 counted runs, one unrecorded smoke run of the Storage file passed 19/19. Its log was discarded.

## The control failure, verbatim (control-01, control-04 and control-05)

```
tests/test_document_source_objects_postgres.py:224:
src/argus/domain/ingestion/documents/service.py:495: in resume
>           raise DocumentServiceError("document_version_conflict", retryable=True)
E           argus.domain.ingestion.documents.service.DocumentServiceError: document_version_conflict
```

The sweeper redispatched 4 Storage-test connections across the 5 runs (runs/control-sweeper.log); only Storage tests used this database. This independently confirms the earlier diagnosis. A real-clock sweeper on the same database requeues drafts the Storage tests leased on the fixed 2026-09-20 clock, and the test's `resume` then loses its version check.

## Session proof

- Start (pg-activity-start.txt, 21:50:28Z). 11 sessions besides my psql. All of them belong to the stack's own containers: pg_net and pg_cron background workers, PostgREST 192.168.192.7, Storage 192.168.192.8, Realtime 192.168.192.6. None came from the Docker gateway 192.168.192.1, which is where any host process would appear. No host process held a connection to 57791 or 57792, only Docker's listeners. No process command line names 5779x.
- ps-start.txt: other agents' processes only (uvicorn 58900 and 8611, a pytest in canary-core-checks, a shell in business-pilot-chattools). None targets this stack.
- Between sets (pg-activity-between.txt), after the 40 runs (pg-activity-end.txt, 21:53:45Z) and after the control (pg-activity-after-control.txt). Same stack sessions plus two "Supabase Storage API 1.77.0" pool connections from the Storage container 192.168.192.8, opened when the tests first used Storage. No host-originated session, and no leftover test session. `financial_document_extractions`, `storage.objects` and `auth.users` all held 0 rows after the runs.
- The worktree stayed clean (`git status --ignored` empty).

## Reading

The 40 clean runs show that, with no foreign sweeper, both named tests are stable on local Storage and the jobs file no longer leaves sweepers behind in its own process. The control shows the failure is not intrinsic to the Storage test. It needs a sweeper outside the test's process on the same database. #924 removes the one in-process way to get that. The cross-process way remains: any second pytest process running the jobs file against the same database. See audit.md.

## Teardown

`supabase stop --no-backup` (stack/stop.log). Afterwards zero containers, volumes and networks matched `storageproof`, and ports 57791-57794 had no listener.
