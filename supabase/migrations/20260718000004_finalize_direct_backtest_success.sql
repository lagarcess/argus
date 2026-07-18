-- #230: direct-route success finalization is one database transaction.
--
-- finalize_direct_backtest_success locks and verifies the owner-scoped
-- direct job, then either: replays the terminal row untouched when
-- reconciliation already won (no Run is created or returned), fails closed
-- when the job row is missing, or creates/replays the canonical Run/evidence
-- tuple via finalize_backtest_completion and links + succeeds the job — all
-- in the same transaction, so a reconciler decision and a late success can
-- never both win.

create or replace function public.finalize_direct_backtest_success(
  p_user_id uuid,
  p_job_id uuid,
  p_execution_identity text,
  p_run jsonb,
  p_idea jsonb,
  p_idea_version jsonb,
  p_evidence_artifact jsonb
) returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_job public.backtest_jobs%rowtype;
  v_tuple record;
begin
  select * into v_job
    from public.backtest_jobs
   where id = p_job_id
     and user_id = p_user_id
   for update;

  if not found then
    -- Fail closed: no admitted owner-scoped job row, no Run.
    return jsonb_build_object('outcome', 'missing');
  end if;

  if v_job.status not in ('queued', 'running') then
    -- Reconciliation already won; the terminal decision is final.
    return jsonb_build_object('outcome', 'superseded', 'job', to_jsonb(v_job));
  end if;

  select * into v_tuple
    from public.finalize_backtest_completion(
      p_user_id,
      p_execution_identity,
      p_run,
      p_idea,
      p_idea_version,
      p_evidence_artifact
    );

  update public.backtest_jobs
     set status = 'succeeded',
         result_run_id = (v_tuple.run ->> 'id')::uuid,
         failure_code = null,
         failure_detail = null,
         retryable = false,
         finished_at = now(),
         updated_at = now()
   where id = p_job_id
   returning * into v_job;

  return jsonb_build_object(
    'outcome', 'finalized',
    'job', to_jsonb(v_job),
    'run', v_tuple.run,
    'idea', v_tuple.idea,
    'idea_version', v_tuple.idea_version,
    'evidence_artifact', v_tuple.evidence_artifact
  );
end;
$$;

revoke all on function public.finalize_direct_backtest_success(
  uuid, uuid, text, jsonb, jsonb, jsonb, jsonb
) from public, anon, authenticated;
grant execute on function public.finalize_direct_backtest_success(
  uuid, uuid, text, jsonb, jsonb, jsonb, jsonb
) to service_role;
