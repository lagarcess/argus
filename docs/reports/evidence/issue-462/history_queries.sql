-- #462: existing production telemetry, prior to the measured cohort.
-- Executed with default_transaction_read_only=on and a 15-second statement timeout.
-- %(cutoff)s is fixed to the live cohort's provenance.started_at.
-- Quantiles here concern recorded call/runtime durations, NEVER first-token timing.
-- query: coverage
SELECT count(*) AS receipt_rows,
       count(DISTINCT metadata->>'request_id') AS correlated_requests,
       count(*) FILTER (WHERE metadata->>'request_id' IS NULL) AS uncorrelated_rows,
       count(*) FILTER (WHERE metadata->'turn_execution'->>'elapsed_seconds' IS NOT NULL) AS runtime_clock_rows
FROM public.route_receipts
WHERE created_at >= %(cutoff)s::timestamptz - interval '30 days' AND created_at < %(cutoff)s::timestamptz;
-- query: tiers
SELECT tier, count(*) AS receipt_rows,
       count(*) FILTER (WHERE outcome = 'succeeded') AS successful_receipts,
       count(DISTINCT metadata->>'request_id') FILTER (WHERE outcome='succeeded') AS successful_requests,
       count(DISTINCT metadata->>'request_id') AS correlated_requests,
       count(*) FILTER (WHERE metadata->>'request_id' IS NULL) AS uncorrelated_rows
FROM public.route_receipts
WHERE created_at >= %(cutoff)s::timestamptz - interval '30 days' AND created_at < %(cutoff)s::timestamptz
GROUP BY tier ORDER BY receipt_rows DESC;
-- query: tasks
SELECT task, schema_name, tier, model, outcome, count(*) AS receipt_rows,
       percentile_disc(0.50) WITHIN GROUP (ORDER BY latency_ms) AS call_p50_ms,
       percentile_disc(0.95) WITHIN GROUP (ORDER BY latency_ms) AS call_p95_ms
FROM public.route_receipts
WHERE created_at >= %(cutoff)s::timestamptz - interval '30 days' AND created_at < %(cutoff)s::timestamptz
GROUP BY task, schema_name, tier, model, outcome ORDER BY receipt_rows DESC;
-- query: turn_runtime
WITH per_request AS (
 SELECT metadata->>'request_id' AS request_id,
        max((metadata->'turn_execution'->>'elapsed_seconds')::numeric) * 1000 AS elapsed_ms
 FROM public.route_receipts
 WHERE created_at >= %(cutoff)s::timestamptz - interval '30 days' AND created_at < %(cutoff)s::timestamptz
   AND metadata->>'request_id' IS NOT NULL
 GROUP BY metadata->>'request_id'
)
SELECT count(*) AS requests, count(elapsed_ms) AS measured_requests,
       percentile_disc(0.50) WITHIN GROUP (ORDER BY elapsed_ms) AS runtime_p50_ms,
       percentile_disc(0.95) WITHIN GROUP (ORDER BY elapsed_ms) AS runtime_p95_ms
FROM per_request;
-- query: research
SELECT metadata->'research'->>'shape' AS shape,
       metadata->'research'->'usage'->>'cache_status' AS cache_status,
       metadata->'research'->'degraded'->>'code' AS degraded,
       count(*) AS assistant_messages,
       percentile_disc(0.50) WITHIN GROUP (ORDER BY (metadata->'research'->'usage'->>'latency_ms')::numeric) AS provider_p50_ms,
       percentile_disc(0.95) WITHIN GROUP (ORDER BY (metadata->'research'->'usage'->>'latency_ms')::numeric) AS provider_p95_ms
FROM public.messages
WHERE role='assistant' AND metadata ? 'research'
  AND created_at >= %(cutoff)s::timestamptz - interval '30 days' AND created_at < %(cutoff)s::timestamptz
GROUP BY shape, cache_status, degraded ORDER BY assistant_messages DESC;
