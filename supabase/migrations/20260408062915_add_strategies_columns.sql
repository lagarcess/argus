-- 1. Add is_admin and other fields to profiles
ALTER TABLE profiles
ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS theme TEXT DEFAULT 'dark',
ADD COLUMN IF NOT EXISTS lang TEXT DEFAULT 'en',
ADD COLUMN IF NOT EXISTS backtest_quota INTEGER DEFAULT 100,
ADD COLUMN IF NOT EXISTS last_quota_reset TIMESTAMPTZ DEFAULT now(),
ADD COLUMN IF NOT EXISTS feature_flags JSONB DEFAULT '{}'::jsonb;

-- Index for is_admin performance
CREATE INDEX IF NOT EXISTS idx_profiles_is_admin ON profiles(is_admin);

-- 2. Modify strategies table to match the contract
-- We add the new columns first
ALTER TABLE strategies
ADD COLUMN IF NOT EXISTS symbol TEXT,
ADD COLUMN IF NOT EXISTS timeframe TEXT,
ADD COLUMN IF NOT EXISTS start_date TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS end_date TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS entry_criteria JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS exit_criteria JSONB DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS indicators_config JSONB DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS patterns TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS executed_at TIMESTAMPTZ;

-- Drop the old config column
ALTER TABLE strategies DROP COLUMN IF EXISTS config;

-- 3. Enable RLS on strategies
ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;

-- 4. RLS Policies for strategies (User owns their data, or is_admin = true)
CREATE POLICY "Users can view their own strategies or admins can view all." ON strategies
    FOR SELECT USING (auth.uid() = user_id OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND is_admin = true));

CREATE POLICY "Users can insert their own strategies." ON strategies
    FOR INSERT WITH CHECK (auth.uid() = user_id OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND is_admin = true));

CREATE POLICY "Users can update their own strategies." ON strategies
    FOR UPDATE USING (auth.uid() = user_id OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND is_admin = true));

CREATE POLICY "Users can delete their own strategies." ON strategies
    FOR DELETE USING (auth.uid() = user_id OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND is_admin = true));

-- Update profiles RLS to allow admins to see all
DROP POLICY IF EXISTS "Users can view their own profile." ON profiles;
CREATE POLICY "Users can view their own profile or admins can view all." ON profiles
    FOR SELECT USING (auth.uid() = id OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND is_admin = true));

-- 5. Quota Reset Cron Setup (Requires pg_cron extension if on Supabase, but we'll create the function first)
CREATE OR REPLACE FUNCTION reset_monthly_quotas()
RETURNS void AS $$
BEGIN
    UPDATE profiles
    SET backtest_quota =
        CASE
            WHEN subscription_tier = 'pro' THEN 999999
            ELSE 100 -- Default free tier
        END,
        last_quota_reset = now();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
