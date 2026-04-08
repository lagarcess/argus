-- Create the rate limits table
CREATE TABLE IF NOT EXISTS api_rate_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    service TEXT NOT NULL,
    hits INT NOT NULL DEFAULT 1,
    window_start TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_api_rate_limits_user_service ON api_rate_limits(user_id, service);

-- Create the increment_rate_limit RPC function
CREATE OR REPLACE FUNCTION increment_rate_limit(
    target_user_id UUID,
    service_name TEXT,
    limit_value INT,
    window_seconds INT
)
RETURNS TABLE (
    current_hits INT,
    remaining_hits INT,
    reset_time TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER -- Run as admin to bypass RLS
AS $$
DECLARE
    v_hits INT;
    v_window_start TIMESTAMPTZ;
BEGIN
    -- 1. Delete expired records for this user and service
    DELETE FROM api_rate_limits
    WHERE user_id = target_user_id
      AND service = service_name
      AND window_start < now() - (window_seconds || ' seconds')::INTERVAL;

    -- 2. Try to update the existing active window
    UPDATE api_rate_limits
    SET hits = hits + 1
    WHERE user_id = target_user_id
      AND service = service_name
      AND window_start >= now() - (window_seconds || ' seconds')::INTERVAL
    RETURNING hits, window_start INTO v_hits, v_window_start;

    -- 3. If no active window exists, insert a new one
    IF NOT FOUND THEN
        INSERT INTO api_rate_limits (user_id, service, hits, window_start)
        VALUES (target_user_id, service_name, 1, now())
        RETURNING hits, window_start INTO v_hits, v_window_start;
    END IF;

    -- 4. Calculate and return results
    RETURN QUERY
    SELECT
        v_hits,
        GREATEST(0, limit_value - v_hits),
        v_window_start + (window_seconds || ' seconds')::INTERVAL;
END;
$$;
