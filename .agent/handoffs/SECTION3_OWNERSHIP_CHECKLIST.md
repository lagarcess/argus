# Section 3 Ownership Checklist

Branch: `codex/section-3-backtest-engine`

## Allowed File Scope
- `src/argus/domain/engine.py`
- `src/argus/domain/engine/**`
- `src/argus/domain/market_data/**`
- `src/argus/domain/backtest/**`
- `src/argus/analysis/**`
- `tests/section3/**`
- `tests/perf/section3/**`

## Explicitly Prohibited
- `src/argus/api/main.py`
- `src/argus/api/schemas.py`
- `src/argus/domain/supabase_gateway.py`
- `supabase/migrations/**`
- `tests/section4/**`
- `web/**`
- `docs/API_CONTRACT.md`
- `docs/api/openapi.yaml`

## Required Delivery Checks
- [ ] Ownership gate passes: `python .agent/scripts/ownership/verify_branch_ownership.py`
- [ ] No deterministic SHA-based metrics remain in runtime path
- [ ] Historical benchmark series is generated for class-default benchmark
- [ ] Section 3 tests pass (engine realism + benchmark + performance guard)
- [ ] Handoff packet completed from template
