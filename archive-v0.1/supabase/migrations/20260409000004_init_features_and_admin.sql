-- Init Features and Admin Tools: Quotas and Feature Flags
-- Aligned with Argus V1 API Contract

-- 1. Create features table
CREATE TABLE IF NOT EXISTS features (
    id TEXT PRIMARY KEY, -- flag name (e.g. 'multi_asset_beta')
    is_enabled BOOLEAN NOT NULL DEFAULT false,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Row Level Security (RLS)
ALTER TABLE features ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Anyone can view features." ON features;
CREATE POLICY "Anyone can view features." ON features
    FOR SELECT USING (true);

DROP POLICY IF EXISTS "Only admins can modify features." ON features;
CREATE POLICY "Only admins can modify features." ON features
    FOR ALL USING (public.is_admin());

-- 2. Quota Management Functions
CREATE OR REPLACE FUNCTION public.reset_monthly_quotas()
RETURNS void AS $$
BEGIN
    UPDATE public.profiles
    SET backtest_quota =
        CASE
            WHEN subscription_tier = 'pro' THEN 999999
            WHEN subscription_tier = 'max' THEN 999999
            ELSE 50
        END,
        remaining_quota =
        CASE
            WHEN subscription_tier = 'pro' THEN 999999
            WHEN subscription_tier = 'max' THEN 999999
            ELSE 50
        END,
        last_quota_reset = now();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 3. Seed initial features
INSERT INTO features (id, is_enabled, description)
VALUES
    ('multi_asset_beta', false, 'Enable multi-asset backtesting beta functionality'),
    ('advanced_harmonics', true, 'Enable advanced harmonic pattern detection')
ON CONFLICT (id) DO NOTHING;
