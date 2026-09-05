-- SELECT-only production readback for the incident. Does not call admission,
-- reset, claim, or any other function that mutates product state.
select c.id as conversation_id, a.is_anonymous,
       w.created_at as workspace_created_at, w.expires_at,
       c.created_at as conversation_created_at, w.updated_at as workspace_updated_at,
       u.created_at as counter_created_at, u.updated_at as last_charge_at,
       u.used_count, u.limit_count, u.period,
       (u.period_start = w.created_at and u.period_end = w.expires_at) as exact_window,
       (select count(*) from public.backtest_jobs j where j.user_id = c.user_id) as jobs,
       (select count(*) from public.backtest_runs r where r.user_id = c.user_id) as runs,
       (select jsonb_agg(jsonb_build_object('created_at', r.created_at, 'outcome', r.outcome))
          from public.route_receipts r
         where r.user_id = c.user_id and r.task = 'result_summary'
           and r.created_at < c.created_at) as earlier_result_summaries
  from public.conversations c
  join auth.users a on a.id = c.user_id
  join public.guest_workspaces w on w.user_id = c.user_id
  join public.usage_counters u on u.user_id = c.user_id
       and u.resource = 'backtest_runs' and u.period = 'guest_session'
 where c.id = '623011f3-7b89-4b1d-b6c3-cd7a99300c8c';

select count(*) as reservations_all_owners
  from public.backtest_jobs
 where idempotency_key = 'confirmation-74e50675-aacc-4ee3-bde1-fa19af92cacc';

select proname, md5(pg_get_functiondef(oid)) as definition_md5
  from pg_proc
 where pronamespace in ('public'::regnamespace, 'argus_private'::regnamespace)
   and proname in ('admit_backtest_job', 'validated_usage_windows',
                   'replace_guest_conversation');
