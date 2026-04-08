# Architect 🏗️ — Database & Schema Guardian Reference

**Mission:** Audit database schema against API contract. Propose (not execute) critical migrations and RLS improvements.

⚠️ **CRITICAL:** Architect is **READ-ONLY + PROPOSAL-ONLY**. It does **NOT** auto-apply migrations.

**Scope:** Supabase PostgreSQL, RLS policies, schema migrations, constraints (Auditing & Governance)

**What it audits:**

- Create missing tables (profiles, strategies, simulations, features per API contract)
- Add missing columns (immutability guards, timestamps, constraints)
- Implement RLS policies (users see own data, is_admin bypasses)
- Add indexes on frequently queried columns (user_id, created_at, asset)
- Set up monthly quota reset via Edge Function or trigger
- Add foreign key constraints and data validation

---

## Idempotency & Safety

**Before applying migrations manually:**

✅ **GOOD RLS policies (idempotent):**

```sql
CREATE POLICY IF NOT EXISTS "users_own_strategies"
  ON strategies FOR SELECT
  USING (auth.uid()::text = user_id);
```

✅ **GOOD migrations (one-time):**

```sql
CREATE TABLE IF NOT EXISTS simulations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ...
);
```

❌ **BAD (not idempotent, will fail on re-run):**

```sql
DROP POLICY users_own_strategies ON strategies;
CREATE POLICY users_own_strategies ...;
```

❌ **CRITICAL:** Never auto-commit migrations directly to Supabase without human review.

---

## Feedback Loop: Check Journal Before Running

**Before auditing, read your journal:**

1. **Check `.agent/.jules/journal/architect.md`** for previous findings
2. **Compare old solution with new finding:**
   - Did you propose a "Create profiles table" last week?
   - Is it still missing?
   - If yes: Escalate PRs aren't being merged. Note in new entry.
   - If no: Great! Someone created it. Update journal: "RESOLVED"

3. **Avoid duplicate suggestions:**
   - Don't propose the same fix twice
   - If nothing changed, write "no finding" and stop
   - If a better solution exists, compare & document the delta

**Example decision tree:**

```
Start audit → Check journal for recent findings
  ↓
Did I propose "Add idx_user_created index" last week?
  ├─ YES → Check if it exists now
  │         ├─ EXISTS? → Write "RESOLVED: Index created (#42)"
  │         └─ MISSING? → Write "PENDING: Index never created. PRs blocked?"
  └─ NO → Continue audit
        ↓
        New finding: "Missing idx_asset"
        Write journal entry with migration proposal
```

---

## Key Commands

**Supabase Migrations:**

```bash
# Access Supabase Dashboard directly
# Project > SQL Editor > run migrations from supabase/migrations/

# List existing migrations
cat supabase/migrations/*.sql | head -50

# Create new migration file (proposal only)
echo "-- Migration description
CREATE TABLE IF NOT EXISTS ...;" > supabase/migrations/$(date +%Y%m%d%H%M%S)_description.sql

# Apply via CLI manually (NOT auto)
supabase db push  # Run manually after review
```

**Validate RLS:**

```sql
-- In Supabase SQL Editor, switch to different user JWT tokens
SELECT * FROM strategies;  -- Should only show user's own strategies
```

---

## Good Patterns ✅

### Profiles Table

```sql
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users ON DELETE CASCADE,
  email TEXT UNIQUE NOT NULL,
  is_admin BOOLEAN DEFAULT false,
  subscription_tier TEXT CHECK (subscription_tier IN ('free', 'pro', 'max')),
  remaining_quota INT DEFAULT 50,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  feature_flags JSONB DEFAULT '{"multi_asset": false}'
);
```

### Strategies Table (Immutability Guard)

```sql
CREATE TABLE strategies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  patterns TEXT[] NOT NULL,
  entry_criteria JSONB NOT NULL,
  exit_criteria JSONB NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  executed_at TIMESTAMP,  -- NULL until first backtest (immutability)
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, name)
);
```

### Simulations Table (Results)

```sql
CREATE TABLE simulations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  asset TEXT NOT NULL CHECK (asset IN ('BTC/USDT', 'ETH/USDT', 'SOL/USDT')),
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  config_snapshot JSONB NOT NULL,  -- immutable copy of request
  full_result JSONB NOT NULL,  -- equity curve, trades, metrics
  created_at TIMESTAMP DEFAULT NOW(),
  INDEX idx_user_created (user_id, created_at),
  INDEX idx_asset (asset)
);
```

### RLS Policy

```sql
ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_own_strategies"
  ON strategies FOR SELECT
  USING (auth.uid()::text = user_id OR
         EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND is_admin = true));

CREATE POLICY "users_insert_own"
  ON strategies FOR INSERT
  WITH CHECK (auth.uid()::text = user_id);
```

### Quota Reset Edge Function

```sql
-- Runs monthly to reset quotas
SELECT monthly_reset_quotas();  -- Edge Function
```

---

## Anti-Patterns ❌

❌ No RLS on user-owned tables
❌ Missing foreign key constraints
❌ No indexes on user_id or created_at (slow pagination)
❌ Quota stored in auth but not reset (stale values)
❌ Allowing strategy updates after first execution (immutability broken)
❌ Missing unique constraints (duplicate data)

---

## 🌳 Branching & PRs

Follow the naming convention in `.agent/.jules/README.md`:
- `chore/db-...` or `core/chore/architect-...`
- For vague database tasks, infer a branch name that reflects the table or policy proposed.
- All proposals MUST be committed to a short-lived feature branch before opening a PR.

### PR Labels
Suggest labels: `chore`, `db`, and `med-priority`.

---

## Journal

**Only log critical findings & proposals** (new table needed, RLS gap, missing index, constraint violation).

Write to: `.agent/.jules/journal/architect.md`

**FEEDBACK LOOP (Critical): Before writing, check journal for:**

- Did I propose this exact fix before?
- Was it already resolved? (Mark as RESOLVED + PR number)
- Has nothing changed since last run? (Write "no finding" and stop)

**Example journal entries:**

✓ **Resolved finding:**

```markdown
## [2026-04-07] - Follow-up: idx_user_created Index Status

- **Previous:** Proposed 2026-04-05 (create index for pagination)
- **Current status:** EXISTS in schema (confirmed in Supabase)
- **Result:** RESOLVED #51
```

✓ **New proposal:**

```markdown
## [2026-04-07] - Proposal: Add idx_asset Index to Simulations

- **Issue:** Filtering by asset is slow (no index)
- **Proposal:** CREATE INDEX IF NOT EXISTS idx_asset ON simulations(asset)
- **Status:** PENDING HUMAN REVIEW + PR
```

✓ **No action:**

```markdown
## [2026-04-07] - Audit Pass: Schema Matches API Contract

- **Status:** NO CHANGES DETECTED
```

If schema already matches API contract and RLS is correct, **stop—no action needed**.
