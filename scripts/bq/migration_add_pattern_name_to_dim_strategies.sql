-- Migration Script: Add pattern_name to dim_strategies for backward compatibility normalization
-- Ref: Issue #365

ALTER TABLE `{{PROJECT_ID}}.crypto_analytics.dim_strategies`
ADD COLUMN IF NOT EXISTS pattern_name STRING;
