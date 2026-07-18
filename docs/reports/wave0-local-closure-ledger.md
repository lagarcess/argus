# Wave 0 Local Closure Ledger

Status: **LOCAL LABORATORY BRANCH — NOT MERGED, NOT PUSHED**

- Worktree: `.claude/worktrees/argus-alpha-audit-c2d919`
- Branch: `claude/argus-alpha-audit-c2d919`
- Base: `390d57294cf9911becdb14ced126770d0124e4cb` (`codex/private-alpha-next` tip)
- Environment: worktree-local `.env` sentinel; every external credential blank;
  `ARGUS_PERSISTENCE_MODE=memory`, `ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture`,
  `ARGUS_CHECKPOINTER_MODE=memory`, `ARGUS_MOCK_AUTH=true`; Python 3.10.20 in-worktree venv.
- Baseline evidence at base SHA: hermetic agent-runtime sweep
  `poetry run pytest tests/agent_runtime tests/test_spine_guardrails.py -q --no-cov`
  → **1129 passed** (41.96s).

State vocabulary (never conflated):

- `LOCAL_ACCEPTANCE_PASS` — criterion proven by deterministic local evidence at the
  named commit.
- `EXTERNAL_GATE_PENDING` — criterion requires deploy/live/paid/founder/QA-database
  authority; recorded precisely, **not claimed**.
- `GENUINE_BLOCKER` — criterion cannot proceed locally for a named technical reason.
- `NOT_APPLICABLE` — criterion does not apply to this branch shape; reason given.
- `REGRESSION_FOUND` — criterion previously held and now fails; must be fixed before
  the checkpoint counts.

No issue is called complete while any `EXTERNAL_GATE_PENDING` item remains.

---

## #234 — OpenAPI generated-vs-checked structural gate

Checkpoint commit: `29cc1e9` — `feat(api): enforce generated-vs-checked OpenAPI structural compatibility`

Changed surfaces: `src/argus/api/openapi_compat.py` (new), `src/argus/api/main.py`
(custom `app.openapi()` post-processor), `scripts/generate_openapi_artifact.py` (new),
`docs/api/openapi.yaml` (regenerated, 2,516 lines), `tests/test_openapi_compatibility.py`
(new, 11 tests), `tests/test_alpha_artifacts.py` (two textual tests upgraded to
structural), `.github/workflows/ci.yml` (gate + artifact guards added to backend list).

Acceptance mapping:

| Criterion | State | Evidence |
| --- | --- | --- |
| Gate parses both artifacts and compares structure, not text | LOCAL_ACCEPTANCE_PASS | `structural_projection` resolves `$ref`s, strips doc-only keys, canonicalizes lists; gate test green |
| Server/path prefix represented exactly once | LOCAL_ACCEPTANCE_PASS | double `/api/v1` fixed (checked file had `servers: /api/v1` + prefixed paths); prefix-once rule + regression test |
| Missing/extra unallowlisted public paths fail | LOCAL_ACCEPTANCE_PASS | negative tests name `GET /api/v1/discovery/assets` (missing) and `GET /api/v1/portfolio-export` (extra) |
| Request/response/required/enum drift fail | LOCAL_ACCEPTANCE_PASS | negative tests for Idempotency-Key required drift, `/me` response schema drift, enum drift |
| Exclusions explicit, minimal, individually named | LOCAL_ACCEPTANCE_PASS | exactly `GET /health`, `GET /internal/readiness`, `POST /api/v1/dev/reset`; test locks the set |
| Streaming differences normalized narrowly | LOCAL_ACCEPTANCE_PASS | only `POST /api/v1/chat/stream` 200 body; request schema + 409/422/429 remain compared |
| Current runtime and checked artifact pass | LOCAL_ACCEPTANCE_PASS | `structural_failures == []` at head; 34 focused tests green |
| Negative tests name the exact difference | LOCAL_ACCEPTANCE_PASS | failure strings carry operation + JSON-pointer path |
| Existing CI runs the gate | LOCAL_ACCEPTANCE_PASS (workflow file) / EXTERNAL_GATE_PENDING (GitHub Actions run) | `ci.yml` backend list now includes the gate; an actual Actions run requires push, which is out of scope tonight |

Reconciled drift (all previously invisible to CI): double `/api/v1` prefix; three
public routes missing from the checked file (`/chat/starter-prompts`,
`/discovery/assets`, `/discovery/indicators`); param-name drift (`{id}` vs
`{conversation_id}` etc.); untruthful generated declarations (Idempotency-Key
declared optional while runtime enforces 400 `idempotency_key_required`; 422
declared as `HTTPValidationError` while the handler returns RFC 9457; chat/stream
declared `application/json` 200 while runtime streams SSE; real 409/429 undeclared).

Focused commands: gate+guards+CI-workflow suites → 34 passed; API suites
(`test_alpha_api_supabase.py`, `test_api_import_boundary.py`,
`test_private_launch_hardening.py`) → 75 passed; ruff + format clean; modularity
budget clean; `git diff --check` clean.

Rollback boundary: revert `29cc1e9` (artifact + gate + declarations revert together).

External gates remaining: one GitHub Actions run of the amended backend list on the
eventually-pushed candidate.
