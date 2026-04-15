-- Add AI Drafting Quotas to Profiles
-- Aligned with Agentic AI Drafting MVP

-- 1. Add columns to profiles
ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS ai_draft_quota INTEGER NOT NULL DEFAULT 5,
ADD COLUMN IF NOT EXISTS remaining_ai_draft_quota INTEGER NOT NULL DEFAULT 5;

COMMENT ON COLUMN public.profiles.ai_draft_quota IS 'Total AI strategy drafts allowed per day/period.';
COMMENT ON COLUMN public.profiles.remaining_ai_draft_quota IS 'Remaining AI strategy drafts for the current period.';

-- 2. Create RPC for atomic AI quota decrement
CREATE OR REPLACE FUNCTION public.decrement_ai_draft_quota(user_uuid UUID)
RETURNS void AS $$
DECLARE
    current_quota INTEGER;
BEGIN
    SELECT remaining_ai_draft_quota INTO current_quota
    FROM public.profiles
    WHERE id = user_uuid;

    IF current_quota <= 0 THEN
        RAISE EXCEPTION 'AI quota exhausted' USING ERRCODE = 'P0001';
    END IF;

    UPDATE public.profiles
    SET remaining_ai_draft_quota = remaining_ai_draft_quota - 1
    WHERE id = user_uuid;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 3. Ensure the generic decrement_user_quota exists (fixing potential missing migration)
CREATE OR REPLACE FUNCTION public.decrement_user_quota(user_uuid UUID)
RETURNS void AS $$
DECLARE
    current_quota INTEGER;
BEGIN
    SELECT remaining_quota INTO current_quota
    FROM public.profiles
    WHERE id = user_uuid;

    IF current_quota <= 0 THEN
        RAISE EXCEPTION 'quota_exhausted' USING ERRCODE = 'P0001';
    END IF;

    UPDATE public.profiles
    SET remaining_quota = remaining_quota - 1
    WHERE id = user_uuid;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
