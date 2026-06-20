# P1 Red Audit Recovery Plan

## Goal

Complete P1 on `codex/private-alpha-next-reintegration` without promotion.
This plan converts the red audit into scoped, reversible implementation work.

P1 remains limited to:

- Idea / IdeaVersion / EvidenceArtifact / DecisionNote spine.
- Automatic evidence capture from completed backtests.
- Explicit current DecisionNote capture.
- Omnisearch-ledger recall with artifact-first previews/actions.
- Docs/API/data-model consistency.
- Measurement-only observability envelope.
- Focused tests and local browser QA.

Out of scope:

- Generic memory/RAG/vector search.
- Broker/export execution.
- Public excerpts implementation.
- Voice/STT provider implementation.
- Research Lab.
- Standalone ledger dashboard.
- PostHog dashboard/product analytics buildout.
- Append-only decision history.
- Broad strategy/collection revival.

## Stop Criteria

Stop and report if:

- API error semantics require a product decision not already covered by docs.
- Supabase durable semantics become unproven.
- Omnisearch requires a new artifact detail route.
- Frontend starts inventing artifact state instead of rendering backend truth.
- Agent runtime absorbs P1 sidecars.
- P0 continuity tests regress.
- The slice stops being cleanly revertable.

## Recovery Slices

### 1. API Error Contract

Root cause:

- `main.py` only normalizes `HTTPException`; FastAPI request validation errors
  still return default envelopes.
- `routers/evidence.py` catches broad `ValueError` and maps durable integrity
  failures to `404 not_found`.

Implementation:

- Add a global `RequestValidationError` handler that returns RFC 9457-style
  Problem Details.
- Add typed evidence-domain errors so only missing/not-owned artifacts map to
  404.
- Map durable decision integrity failures to internal Problem Details.

Tests:

- Invalid decision POST body returns Problem Details.
- Missing/not-owned evidence returns 404 Problem Details.
- Durable decision failure returns non-404 Problem Details.

### 2. Evidence Payload And Preview Completeness

Root cause:

- Evidence payload captures digest, assumptions, metrics, sanitized result card,
  chart summary, and provenance, but quick-take/breakdown context is not first
  class where available.
- Search preview is safe but too thin for artifact-first recall.

Implementation:

- Extend evidence payload with `quick_take` and `breakdown` fields when source
  run/card metadata already has safe content.
- Enrich preview with sanitized assumptions, metric summary, quick take, and
  breakdown excerpt where present.
- Keep internal ids, route receipts, provider/model metadata, retry payloads,
  transcripts, and context packets out of previews.

Tests:

- Evidence payload includes assumptions, metrics, provenance, digest, result
  card, and optional quick-take/breakdown fields.
- Search preview exposes safe artifact summary fields and no internal ids.

### 3. Omnisearch Artifact-First UX

Root cause:

- Search rows still behave like conversations.
- Right panel copy and actions are conversation-first.
- Artifact rows lack artifact-aware actions and mobile preview coverage.

Implementation:

- Keep the modal as the P1 artifact preview surface; do not add a new route.
- For chat rows, Enter/click opens the conversation.
- For artifact rows, Enter/click selects/updates the preview panel and keeps the
  overlay open.
- Show source conversation as provenance in the panel footer.
- Keep destructive rename/archive/delete actions conversation-only.
- Add safe artifact actions only where a real P1 action exists. For P1, source
  conversation navigation is the stable action; decision mutation stays on the
  result card.
- Replace conversation-specific empty/preview copy with artifact-aware copy.
- Ensure the preview exists on mobile.

Tests:

- Search normalization keeps typed artifact rows artifact-first.
- Artifact row activation does not call conversation navigation.
- Chat row activation still opens conversation.
- Conversation-only hover actions do not appear on evidence-like rows.
- Locale keys map P1 nouns and decision labels without raw enums.

### 4. Measurement-Only Observability Envelope

Root cause:

- The decision memo and roadmap put a measurement envelope in P1 scope.
- Current branch has operational route receipts but no P1 event/cost/eval
  contract.

Implementation:

- Add pure non-emitting observability contract models and sanitizers.
- Add privacy ladder: `raw_alpha`, `redacted_default`, `metadata_only`,
  `disabled`.
- Add event/category enums covering evidence capture, decision capture, recall,
  continuity mismatch, cost ledger, and eval readiness.
- Keep live analytics sinks and durable telemetry/cost/eval tables deferred.
- Do not introduce PostHog runtime emission.

Tests:

- Contract models validate required event fields.
- Sanitizer strips never-send keys in every privacy mode.
- Measurement gate explicitly reports `live_analytics_sink_enabled = false`.

### 5. Docs Alignment

Implementation:

- Update `API_CONTRACT.md` for Problem Details validation, decision errors,
  typed search, and P1 preview boundaries.
- Update `DATA_MODEL.md` for payload and lifecycle semantics.
- Update `ARCHITECTURE.md` for P1 canonical objects and measurement envelope.
- Update `docs/specs/private-alpha-next-roadmap.md` status/checklist to match
  actual verification state.

Tests:

- Run existing docs/contract guard tests if present.
- Include docs in final diff review.

## Verification Gate

Required before any promotion discussion:

- Focused backend P1 tests.
- Focused frontend Omnisearch/result-card tests.
- Focused P0 continuity tests if touched surfaces can affect P0.
- `git diff --check`.
- Live local browser QA:
  - messy prompt -> confirmation -> run -> result;
  - add decision -> hard reload;
  - Omnisearch recalls Conversation, Backtest, Evidence, Decision, Idea;
  - artifact rows preview artifacts and show source conversation as provenance;
  - no duplicate ready/result cards;
  - no raw internal fields leak;
  - language switch and new-chat async navigation smoke;
  - P0 add/append/replace and benchmark continuity smoke.

## Commit Discipline

Use small conventional commits:

1. API error contract.
2. Evidence payload/search preview.
3. Omnisearch artifact-first UI.
4. Measurement-only observability envelope.
5. Docs alignment.

Do not promote, push, merge, or open a PR without explicit founder signoff.
