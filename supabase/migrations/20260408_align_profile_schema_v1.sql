ALTER TABLE public.profiles RENAME COLUMN tier TO subscription_tier;
ALTER TABLE public.profiles DROP COLUMN IF EXISTS backtest_limit;
