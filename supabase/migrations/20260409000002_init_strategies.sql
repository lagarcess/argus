-- Init Strategies: V1 Criteria-based strategy storage
-- Aligned with Argus V1 API Contract

CREATE TABLE IF NOT EXISTS strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    symbol TEXT,
    timeframe TEXT,
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    entry_criteria JSONB DEFAULT '[]'::jsonb,
    exit_criteria JSONB DEFAULT '{}'::jsonb,
    indicators_config JSONB DEFAULT '{}'::jsonb,
    patterns TEXT[] DEFAULT '{}'::text[],
    executed_at TIMESTAMPTZ, -- Not null means the strategy is immutable
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for user lookups
CREATE INDEX IF NOT EXISTS idx_strategies_user_id ON strategies(user_id);

-- Row Level Security (RLS)
ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own strategies or admins can view all." ON strategies;
CREATE POLICY "Users can view their own strategies or admins can view all." ON strategies
    FOR SELECT USING (auth.uid() = user_id OR public.is_admin());

DROP POLICY IF EXISTS "Users can insert their own strategies." ON strategies;
CREATE POLICY "Users can insert their own strategies." ON strategies
    FOR INSERT WITH CHECK (auth.uid() = user_id OR public.is_admin());

DROP POLICY IF EXISTS "Users can update their own strategies." ON strategies;
CREATE POLICY "Users can update their own strategies." ON strategies
    FOR UPDATE USING ((auth.uid() = user_id AND executed_at IS NULL) OR public.is_admin());

DROP POLICY IF EXISTS "Users can delete their own strategies." ON strategies;
CREATE POLICY "Users can delete their own strategies." ON strategies
    FOR DELETE USING ((auth.uid() = user_id AND executed_at IS NULL) OR public.is_admin());
