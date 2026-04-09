-- Init Simulations: V1 Flattened results and snapshot storage
-- Aligned with Argus V1 API Contract

CREATE TABLE IF NOT EXISTS simulations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    strategy_id UUID REFERENCES strategies(id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    config_snapshot JSONB NOT NULL,
    summary JSONB NOT NULL,              -- Top-level metrics (total_return_pct, win_rate, sharpe, etc.)
    reality_gap_metrics JSONB NOT NULL,  -- Slippage/Fee impact
    full_result JSONB NOT NULL,         -- Equity curve + full trades array
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_simulations_user_id ON simulations(user_id);
CREATE INDEX IF NOT EXISTS idx_simulations_strategy_id ON simulations(strategy_id);
CREATE INDEX IF NOT EXISTS idx_simulations_created_at ON simulations(created_at DESC);

-- Row Level Security (RLS)
ALTER TABLE simulations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own simulations or admins can view all." ON simulations;
CREATE POLICY "Users can view their own simulations or admins can view all." ON simulations
    FOR SELECT USING (auth.uid() = user_id OR public.is_admin());

DROP POLICY IF EXISTS "Users can insert their own simulations." ON simulations;
CREATE POLICY "Users can insert their own simulations." ON simulations
    FOR INSERT WITH CHECK (auth.uid() = user_id OR public.is_admin());

-- Note: Simulations are immutable once created. No UPDATE or DELETE policies for users.
DROP POLICY IF EXISTS "Admins can delete simulations." ON simulations;
CREATE POLICY "Admins can delete simulations." ON simulations
    FOR DELETE USING (public.is_admin());
