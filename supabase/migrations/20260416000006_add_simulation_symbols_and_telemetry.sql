-- Additive migration:
-- 1) Align simulations schema with runtime (`symbols` text[])
-- 2) Add telemetry event sink for private-beta funnel observability

ALTER TABLE simulations
ADD COLUMN IF NOT EXISTS symbols TEXT[];

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'simulations'
          AND column_name = 'symbol'
    ) THEN
        EXECUTE $sql$
            UPDATE simulations
            SET symbols = CASE
                WHEN symbols IS NULL AND symbol IS NOT NULL THEN ARRAY[symbol]
                WHEN symbols IS NULL THEN '{}'::text[]
                ELSE symbols
            END
        $sql$;
    ELSE
        UPDATE simulations
        SET symbols = COALESCE(symbols, '{}'::text[]);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_simulations_symbols_gin
ON simulations USING gin (symbols);

CREATE TABLE IF NOT EXISTS telemetry_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    event TEXT NOT NULL,
    event_ts TIMESTAMPTZ NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_telemetry_events_user_created
ON telemetry_events (user_id, created_at DESC);

ALTER TABLE telemetry_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can insert their own telemetry events." ON telemetry_events;
CREATE POLICY "Users can insert their own telemetry events." ON telemetry_events
    FOR INSERT WITH CHECK (auth.uid() = user_id OR public.is_admin());

DROP POLICY IF EXISTS "Users can view their own telemetry events or admins can view all." ON telemetry_events;
CREATE POLICY "Users can view their own telemetry events or admins can view all." ON telemetry_events
    FOR SELECT USING (auth.uid() = user_id OR public.is_admin());
