-- View: summary_strategy_performance
-- Replaces: src/crypto_signals/pipelines/performance.py + performance_query.sql
-- Issue: #367
--
-- Computes per-strategy performance metrics from the agg_strategy_daily
-- materialized view. Uses PnL-only drawdown (no baseline_capital).
--
-- Placeholders (injected by deploy_bq_views.py):
--   {project_id}  — GCP project ID
--   {env_suffix}   — '_test' for DEV/TEST, '' for PROD
--
-- Metrics produced:
--   - total_trades, win_rate, profit_factor
--   - sharpe_ratio (annualized, 365-day)
--   - sortino_ratio (annualized, downside-only volatility)
--   - max_drawdown_usd (peak-to-trough in dollar terms)
--   - alpha, beta (stubbed to 0.0 pending benchmark index — TODO #315)

CREATE OR REPLACE VIEW `{project_id}.crypto_analytics.summary_strategy_performance{env_suffix}`
AS
WITH daily_strategy_metrics AS (
    -- Aggregate across symbols per strategy per day
    SELECT
        ds,
        strategy_id,
        SUM(total_pnl) AS daily_pnl,
        SUM(trade_count) AS daily_trades,
        -- Explicitly compute daily winning trades for clarity.
        -- (win_rate * trade_count) reconstructs COUNTIF(pnl_usd > 0) from the source MV.
        SUM(win_rate * trade_count) AS daily_wins
    FROM `{project_id}.crypto_analytics.agg_strategy_daily{env_suffix}`
    GROUP BY ds, strategy_id
),
historical_metrics AS (
    -- Running window calculations over the PnL series
    SELECT
        ds,
        strategy_id,
        daily_pnl,
        daily_trades,
        SUM(daily_trades) OVER (PARTITION BY strategy_id ORDER BY ds) AS total_trades,
        -- Cumulative win rate: total wins / total trades
        SAFE_DIVIDE(
            SUM(daily_wins) OVER (PARTITION BY strategy_id ORDER BY ds),
            SUM(daily_trades) OVER (PARTITION BY strategy_id ORDER BY ds)
        ) AS win_rate,
        -- Profit Factor: SUM(Gain) / ABS(SUM(Loss))
        SAFE_DIVIDE(
            SUM(IF(daily_pnl > 0, daily_pnl, 0)) OVER (PARTITION BY strategy_id ORDER BY ds),
            ABS(SUM(IF(daily_pnl < 0, daily_pnl, 0)) OVER (PARTITION BY strategy_id ORDER BY ds))
        ) AS profit_factor,
        -- Annualized Sharpe (365 days for Crypto)
        SAFE_DIVIDE(
            AVG(daily_pnl) OVER (PARTITION BY strategy_id ORDER BY ds),
            STDDEV(daily_pnl) OVER (PARTITION BY strategy_id ORDER BY ds)
        ) * SQRT(365) AS sharpe_ratio,
        -- Annualized Sortino (downside-only volatility)
        SAFE_DIVIDE(
            AVG(daily_pnl) OVER (PARTITION BY strategy_id ORDER BY ds),
            STDDEV(IF(daily_pnl < 0, daily_pnl, NULL)) OVER (PARTITION BY strategy_id ORDER BY ds)
        ) * SQRT(365) AS sortino_ratio,
        -- Cumulative PnL (equity curve from zero)
        SUM(daily_pnl) OVER (PARTITION BY strategy_id ORDER BY ds) AS cum_pnl
    FROM daily_strategy_metrics
),
drawdown_calc AS (
    -- Peak cumulative PnL for drawdown calculation
    SELECT
        *,
        MAX(cum_pnl) OVER (PARTITION BY strategy_id ORDER BY ds) AS peak_cum_pnl
    FROM historical_metrics
),
final_metrics AS (
    SELECT
        ds,
        strategy_id,
        CAST(total_trades AS INT64) AS total_trades,
        win_rate,
        IFNULL(profit_factor, 1.0) AS profit_factor,
        IFNULL(sharpe_ratio, 0.0) AS sharpe_ratio,
        IFNULL(sortino_ratio, 0.0) AS sortino_ratio,
        -- Max drawdown in dollar terms (peak-to-trough cumulative PnL)
        MAX(peak_cum_pnl - cum_pnl) OVER (PARTITION BY strategy_id ORDER BY ds) AS max_drawdown_usd,
        -- TODO(#315): Alpha/Beta require a benchmark index
        0.0 AS alpha,
        0.0 AS beta
    FROM drawdown_calc
)
SELECT * FROM final_metrics;
