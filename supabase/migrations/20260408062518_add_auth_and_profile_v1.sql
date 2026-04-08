-- Add new fields to profiles table
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT false;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS theme TEXT DEFAULT 'dark';
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS lang TEXT DEFAULT 'en';
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS backtest_quota INTEGER DEFAULT 50;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS last_quota_reset TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now());
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS feature_flags JSONB DEFAULT '{}'::jsonb;

-- Create index on is_admin for faster lookups
CREATE INDEX IF NOT EXISTS idx_profiles_is_admin ON profiles(is_admin);

-- Update subscription tier check constraint to include 'max'
ALTER TABLE profiles DROP CONSTRAINT IF EXISTS profiles_subscription_tier_check;
ALTER TABLE profiles ADD CONSTRAINT profiles_subscription_tier_check CHECK (subscription_tier IN ('free', 'pro', 'max'));

-- RLS admin exception policy
-- We use a function to check if the current user is an admin to avoid infinite recursion in policies
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
  SELECT COALESCE(
    (SELECT is_admin FROM public.profiles WHERE id = auth.uid()),
    false
  );
$$ LANGUAGE sql SECURITY DEFINER;

-- Add policies that allow admins to bypass RLS for profiles, strategies, and simulations
-- (Assuming strategies and simulations tables exist or will use this function)
CREATE POLICY "Admins can view all profiles" ON profiles
    FOR SELECT USING (public.is_admin());

CREATE POLICY "Admins can update all profiles" ON profiles
    FOR UPDATE USING (public.is_admin());

CREATE POLICY "Admins can delete all profiles" ON profiles
    FOR DELETE USING (public.is_admin());


-- Update handle_new_user to set initial quotas
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.profiles (
    id,
    subscription_tier,
    is_admin,
    theme,
    lang,
    backtest_quota,
    last_quota_reset,
    feature_flags
  )
  VALUES (
    new.id,
    'free',
    false,
    'dark',
    'en',
    50,
    timezone('utc'::text, now()),
    '{}'::jsonb
  );
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to reset monthly quotas
CREATE OR REPLACE FUNCTION public.reset_monthly_quotas()
RETURNS void AS $$
BEGIN
  -- Reset quota for free users to 50, and update last_quota_reset to current time
  -- In a full implementation, pro/max quotas might differ or be unlimited (represented as a large number or NULL)
  UPDATE public.profiles
  SET
    backtest_quota = CASE
      WHEN subscription_tier = 'free' THEN 50
      WHEN subscription_tier = 'pro' THEN 999999
      WHEN subscription_tier = 'max' THEN 999999
      ELSE 50
    END,
    last_quota_reset = timezone('utc'::text, now());
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Note: To actually run the cron, you would need the pg_cron extension enabled
-- and schedule it. Example:
-- SELECT cron.schedule('0 0 1 * *', $$SELECT public.reset_monthly_quotas()$$);
