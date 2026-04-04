-- scripts/bq/vw_fact_trades.sql
-- Create or replace the view for normalized trade analytics.
-- This view bridges historical rows (where strategy_id is a pattern name)
-- with new rows (where strategy_id is a UUID) by coalescing to a normalized UUID.

CREATE OR REPLACE VIEW `{{PROJECT_ID}}.crypto_analytics.vw_fact_trades` AS
SELECT
    t.*,
    COALESCE(
        -- If strategy_id is already a UUID match, use it
        d_direct.strategy_id,
        -- Otherwise look up by pattern_name in dim_strategies
        d_by_name.strategy_id,
        -- Ultimate fallback: keep the raw value
        t.strategy_id
    ) AS strategy_id_normalized
FROM `{{PROJECT_ID}}.crypto_analytics.fact_trades` t
LEFT JOIN `{{PROJECT_ID}}.crypto_analytics.dim_strategies` d_direct
    ON t.strategy_id = d_direct.strategy_id
   AND d_direct.is_current = TRUE
LEFT JOIN `{{PROJECT_ID}}.crypto_analytics.dim_strategies` d_by_name
    ON t.strategy_id = d_by_name.pattern_name
   AND d_by_name.is_current = TRUE;
