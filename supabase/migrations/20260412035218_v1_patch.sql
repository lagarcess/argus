-- =============================================================================
-- V1 Patch: Multi-Asset Overhaul, Simulation Ratings, Quota Governance
-- Aligned with Argus V1 API Contract
-- Audited against supabase-postgres-best-practices (Rules #4, #5)
-- =============================================================================

-- =============================================================================
-- SECTION A: strategies — symbol (TEXT) → symbols (TEXT[]) + GIN Index
-- =============================================================================

ALTER TABLE public.strategies DROP COLUMN IF EXISTS symbol;

ALTER TABLE public.strategies
    ADD COLUMN symbols TEXT[] NOT NULL DEFAULT '{}';

-- GIN index for high-speed @>, &&, ANY()-based multi-asset searches (Rule #4)
CREATE INDEX IF NOT EXISTS idx_strategies_symbols_gin
    ON public.strategies USING GIN (symbols);


-- =============================================================================
-- SECTION B: simulations — symbol (TEXT) → symbols (TEXT[]) + GIN Index
-- =============================================================================

ALTER TABLE public.simulations DROP COLUMN IF EXISTS symbol;

ALTER TABLE public.simulations
    ADD COLUMN symbols TEXT[] NOT NULL DEFAULT '{}';

-- GIN index for high-speed @>, &&, ANY()-based multi-asset searches (Rule #4)
CREATE INDEX IF NOT EXISTS idx_simulations_symbols_gin
    ON public.simulations USING GIN (symbols);


-- =============================================================================
-- SECTION C: simulation_ratings — Feedback Loop table
-- Captures user ratings on backtest realism, feeds the Reality Gap loop.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.simulation_ratings (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Nullable: rating could theoretically be detached from profile on delete
    user_id         UUID        REFERENCES public.profiles(id) ON DELETE SET NULL,
    -- Cascade on simulation delete — rating is meaningless without the sim
    simulation_id   UUID        NOT NULL REFERENCES public.simulations(id) ON DELETE CASCADE,
    rating          SMALLINT    CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT,
    -- Stores user-reported reality gap observations (slippage, fill quality, etc.)
    reality_gap_metrics JSONB   DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for user lookups
CREATE INDEX IF NOT EXISTS idx_simulation_ratings_user_id
    ON public.simulation_ratings (user_id);

-- Index for simulation lookups (e.g., "show all ratings for this sim")
CREATE INDEX IF NOT EXISTS idx_simulation_ratings_simulation_id
    ON public.simulation_ratings (simulation_id);

-- RLS: Enable immediately after table creation (never leave a table unprotected)
ALTER TABLE public.simulation_ratings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own ratings or admins can view all."
    ON public.simulation_ratings;
CREATE POLICY "Users can view their own ratings or admins can view all."
    ON public.simulation_ratings
    FOR SELECT USING (auth.uid() = user_id OR public.is_admin());

DROP POLICY IF EXISTS "Users can insert their own ratings."
    ON public.simulation_ratings;
CREATE POLICY "Users can insert their own ratings."
    ON public.simulation_ratings
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Ratings are immutable once submitted (no UPDATE/DELETE for users)
DROP POLICY IF EXISTS "Admins can delete ratings." ON public.simulation_ratings;
CREATE POLICY "Admins can delete ratings."
    ON public.simulation_ratings
    FOR DELETE USING (public.is_admin());


-- =============================================================================
-- SECTION D: decrement_user_quota — Upgraded with admin bypass + P0001 raise
--
-- Failure mode: RAISES EXCEPTION with ERRCODE P0001 when quota is exhausted.
-- API layer catches this and returns 402 Payment Required.
-- Admin bypass: admins are NEVER decremented and NEVER blocked.
-- Rule #5: single-row UPDATE is atomic — no explicit lock needed.
-- =============================================================================

CREATE OR REPLACE FUNCTION public.decrement_user_quota(user_uuid UUID)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = '' AS $$
DECLARE
    is_user_admin   BOOLEAN;
    current_quota   INTEGER;
BEGIN
    -- Fetch admin status and quota in a single round-trip
    SELECT is_admin, remaining_quota
      INTO is_user_admin, current_quota
      FROM public.profiles
     WHERE id = user_uuid;

    -- Admin bypass: skip enforcement entirely
    IF is_user_admin THEN
        RETURN;
    END IF;

    -- Quota exhausted: raise exception so API can return 402
    IF current_quota IS NULL OR current_quota <= 0 THEN
        RAISE EXCEPTION 'quota_exhausted'
            USING ERRCODE = 'P0001',
                  DETAIL  = 'User has no remaining quota. Upgrade plan to continue.';
    END IF;

    -- Atomic decrement (single-row UPDATE — no GREATEST() silent swallowing)
    UPDATE public.profiles
       SET remaining_quota = remaining_quota - 1
     WHERE id = user_uuid;
END;
$$;
