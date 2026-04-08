# Database Patterns Skill

**When to use:** Designing Supabase tables, setting up Row-Level Security (RLS), creating migrations, ensuring data integrity and user privacy.

---

## Overview

Argus uses Supabase (PostgreSQL + Auth) as the database. Key principles:

- **RLS First:** Every table has RLS policies; users see only own data
- **Immutability:** Once a strategy executes (`executed_at` set), it cannot be modified
- **Quotas:** `remaining_quota` tracks monthly backtest limit per user
- **Constraints:** Foreign keys, unique indices, check constraints prevent bad data

**Key files:**

- `supabase/migrations/*.sql` – Table definitions, RLS policies, indices
- Supabase Dashboard → SQL Editor – Direct schema queries

---

## Pattern 1: User-Owned Tables with RLS

### ✅ GOOD

```sql
-- Create table with user_id FK
CREATE TABLE strategies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  patterns TEXT[] NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  executed_at TIMESTAMP NULL,  -- Guards immutability
  UNIQUE(user_id, name),  -- No duplicate names per user
  INDEX idx_user_created (user_id, created_at)  -- Pagination
);

-- Enable RLS
ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;

-- Users see only their own strategies
CREATE POLICY "users_own_strategies"
  ON strategies FOR SELECT
  USING (
    auth.uid()::text = user_id OR
    EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND is_admin = true)
  );

-- Users can insert only as themselves
CREATE POLICY "users_create_own_strategies"
  ON strategies FOR INSERT
  WITH CHECK (auth.uid()::text = user_id);

-- Users can update only their own (and only if not executed)
CREATE POLICY "users_update_own_strategies"
  ON strategies FOR UPDATE
  USING (
    auth.uid()::text = user_id AND executed_at IS NULL
  )
  WITH CHECK (auth.uid()::text = user_id);

-- Users can only delete if not executed
CREATE POLICY "users_delete_own_strategies"
  ON strategies FOR DELETE
  USING (auth.uid()::text = user_id AND executed_at IS NULL);
```

### ❌ BAD

```sql
-- ❌ No RLS → everyone sees all data
CREATE TABLE strategies (id UUID, user_id UUID, ...);
-- Missing: ALTER TABLE ... ENABLE ROW LEVEL SECURITY

-- ❌ No checks → garbage data allowed
CREATE TABLE strategies (
  id UUID,
  user_id UUID,
  executed_at TIMESTAMP
  -- No immutability check
);

-- ❌ No indices → slow pagination queries
CREATE TABLE strategies (
  id UUID,
  user_id UUID,
  created_at TIMESTAMP
  -- Missing: INDEX idx_user_created
);
```

---

## Pattern 2: Immutability Pattern

### ✅ GOOD

```sql
-- Once a strategy executes, set executed_at timestamp (immutable signal)
CREATE TABLE strategies (
  id UUID PRIMARY KEY,
  user_id UUID,
  name TEXT,
  executed_at TIMESTAMP NULL,  -- NULL = draft (editable), NOT NULL = frozen
  CONSTRAINT can_only_update_drafts CHECK (executed_at IS NULL OR true)
);

-- Guard against edits after execution
CREATE POLICY "no_update_after_executed"
  ON strategies FOR UPDATE
  USING (executed_at IS NULL)  -- Only update if NOT yet executed
  WITH CHECK (true);

-- In application code:
-- When backtest starts:
UPDATE strategies SET executed_at = NOW() WHERE id = $1;

-- This prevents:
UPDATE strategies SET entry_criteria = ... WHERE executed_at IS NOT NULL;  -- 403 Forbidden
```

### ❌ BAD

```sql
-- ❌ No immutability guard → user could edit strategy after running it
CREATE TABLE strategies (id UUID, entry_criteria JSONB, ...);
-- No executed_at field, no policy blocking updates

-- Application code might have stale snapshots:
backtest = strategies[id]  -- Read strategy once
update_strategy(id, new_data)  -- User edits it
backtest.run()  -- Runs with OLD snapshot, confuses user
```

---

## Pattern 3: Quota Management

### ✅ GOOD

```sql
CREATE TABLE profiles (
  id UUID PRIMARY KEY,
  subscription_tier TEXT CHECK (subscription_tier IN ('free', 'pro', 'max')),
  remaining_quota INT,
  created_at TIMESTAMP DEFAULT NOW(),
  CONSTRAINT quota_non_negative CHECK (remaining_quota >= 0)
);

-- Monthly quota reset via Supabase Edge Function (scheduled)
-- Or run this SQL on 1st of month:
UPDATE profiles
SET remaining_quota = CASE
  WHEN subscription_tier = 'free' THEN 50
  WHEN subscription_tier = 'pro' THEN 500
  ELSE 9999  -- max tier
END
WHERE EXTRACT(DAY FROM NOW()) = 1
  AND EXTRACT(MONTH FROM updated_at) = EXTRACT(MONTH FROM NOW()) - 1;

-- In API: Decrement quota on backtest POST
UPDATE profiles SET remaining_quota = remaining_quota - 1 WHERE id = $user_id;
```

### ❌ BAD

```sql
-- ❌ No quota check → quota could go negative
CREATE TABLE profiles (remaining_quota INT);  -- No constraint

-- ❌ Manual reset (forgotten, causes month-long limits)
-- No monthly Edge Function setup
```

---

## Pattern 4: Shared Data with Admin Override

### ✅ GOOD

```sql
-- Features table (used by all users)
CREATE TABLE features (
  id SERIAL PRIMARY KEY,
  feature_name TEXT UNIQUE,
  enabled BOOLEAN,
  rollout_pct INT CHECK (rollout_pct >= 0 AND rollout_pct <= 100)
);

-- RLS: Everyone can read (no personal data)
ALTER TABLE features ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public_read_features"
  ON features FOR SELECT
  USING (enabled = true);

-- Only admins can modify
CREATE POLICY "admin_write_features"
  ON features FOR UPDATE
  USING (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND is_admin = true));
```

---

## Pattern 5: Foreign Key Constraints

### ✅ GOOD

```sql
-- Cascade delete: removing strategy removes all its backtests
CREATE TABLE strategies (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE simulations (
  id UUID PRIMARY KEY,
  strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE
);

-- Prevents orphaned backtests after strategy delete
```

### ❌ BAD

```sql
-- ❌ No foreign key → orphaned data
CREATE TABLE simulations (
  id UUID,
  strategy_id UUID  -- No REFERENCES, broken link possible
);
```

---

## Rules (Always Follow)

1. **RLS on all tables:** Every table containing user data must have RLS enabled
2. **`user_id` FK:** User-owned tables reference `profiles(id) ON DELETE CASCADE`
3. **Immutability guards:** Use `executed_at` timestamp + policy check
4. **Quotas are serialized:** Decrement atomically (`UPDATE ... SET remaining_quota = remaining_quota - 1`)
5. **Indices on foreign keys:** LTE performance (e.g., `idx_user_created` on `(user_id, created_at)` for pagination)
6. **Check constraints:** Enforce domain rules in DB (e.g., `quota >= 0`, `tier IN (...)`)

---

## Testing RLS

```sql
-- In Supabase SQL Editor, test as different users:

-- 1. User A's JWT token → should see own data
SELECT auth.uid();  -- Returns user-a-uuid

SELECT * FROM strategies;  -- Only user A's strategies

-- 2. Switch JWT token to User B
SELECT * FROM strategies;  -- Only user B's strategies, can't see user A's

-- 3. Test immutability
UPDATE strategies SET name = 'Hacked' WHERE id = '...' AND executed_at IS NOT NULL;
-- Should fail with: "new row violates row-level security policy"
```

---

## Common Migrations

**Create profile:**

```sql
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users,
  email TEXT UNIQUE,
  is_admin BOOLEAN DEFAULT false,
  subscription_tier TEXT DEFAULT 'free',
  remaining_quota INT DEFAULT 50,
  created_at TIMESTAMP DEFAULT NOW()
);
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
```

**Create strategies:**

```sql
CREATE TABLE strategies (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES profiles(id),
  name TEXT NOT NULL,
  entry_criteria JSONB,
  patterns TEXT[],
  executed_at TIMESTAMP,
  INDEX idx_user_created (user_id, created_at)
);
ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;
```

---

## Examples in This Project

- `supabase/migrations/` – All table migrations
- [API Contract](../docs/api_contract.md) – Database schema section
- `.agent/agents/architect.md` – Database improvement tasks
