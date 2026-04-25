# Section 4 Ownership Checklist

Branch: `codex/section-4-persistence-model`

## Allowed File Scope
- `src/argus/api/main.py`
- `src/argus/api/schemas.py`
- `src/argus/domain/supabase_gateway.py`
- `supabase/migrations/**`
- `tests/test_alpha_api.py`
- `tests/test_alpha_api_supabase.py`
- `tests/section4/**`
- `web/lib/argus-api.ts`
- `web/components/chat/ChatInterface.tsx`
- `web/components/chat/ChatInput.tsx`

## Explicitly Prohibited
- `src/argus/domain/engine.py`
- `src/argus/domain/engine/**`
- `src/argus/domain/market_data/**`
- `src/argus/domain/backtest/**`
- `src/argus/analysis/**`
- `tests/section3/**`
- `docs/API_CONTRACT.md`
- `docs/api/openapi.yaml`

## Required Delivery Checks
- [ ] Ownership gate passes: `python .agent/scripts/ownership/verify_branch_ownership.py`
- [ ] Runs persist to and load from Supabase-backed path
- [ ] `config_snapshot` persists normalized defaults used for execution
- [ ] Same-asset violations return RFC9457-style `422` payload
- [ ] Section 4 tests pass (persistence round-trip + snapshot completeness + mixed-asset + chat-stream persistence)
- [ ] Handoff packet completed from template
