-- Alignment Migration: Schema V1.1
-- Purpose: Aligns persistence layer with api_contract.md

-- 1. Ensure Profiles has the master is_admin flag and quota fields
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT false;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS backtest_quota INTEGER DEFAULT 50;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS remaining_quota INTEGER DEFAULT 50;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS last_quota_reset TIMESTAMPTZ DEFAULT now();

-- 2. Cleanup and Re-create Simulations Table
DROP TABLE IF EXISTS simulations;

CREATE TABLE simulations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    strategy_id UUID REFERENCES strategies(id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    config_snapshot JSONB NOT NULL,
    summary JSONB NOT NULL,              -- Top-level metrics (pnl, win_rate, sharpe)
    reality_gap_metrics JSONB NOT NULL,  -- Slippage/Fee impact
    full_result JSONB NOT NULL,         -- Equity curve + full trades array
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Update Strategies Table (if missing RLS or specific columns)
ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;

-- 4. Enable RLS on Simulations
ALTER TABLE simulations ENABLE ROW LEVEL SECURITY;

-- 5. Policies for Simulations
DROP POLICY IF EXISTS "Users can view their own simulations." ON simulations;
CREATE POLICY "Users can view their own simulations." ON simulations
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own simulations." ON simulations;
CREATE POLICY "Users can insert their own simulations." ON simulations
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- 6. Policies for Strategies
DROP POLICY IF EXISTS "Users can view their own strategies." ON strategies;
CREATE POLICY "Users can view their own strategies." ON strategies
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own strategies." ON strategies;
CREATE POLICY "Users can insert their own strategies." ON strategies
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own strategies." ON strategies;
CREATE POLICY "Users can update their own strategies." ON strategies
    FOR UPDATE USING (auth.uid() = user_id);

-- 7. Indexes
CREATE INDEX IF NOT EXISTS idx_simulations_user_id ON simulations(user_id);
CREATE INDEX IF NOT EXISTS idx_simulations_strategy_id ON simulations(strategy_id);
CREATE INDEX IF NOT EXISTS idx_simulations_created_at ON simulations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategies_user_id ON strategies(user_id);
