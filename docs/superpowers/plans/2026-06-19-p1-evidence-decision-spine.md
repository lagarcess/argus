# P1 Evidence Decision Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the P1 Idea, IdeaVersion, EvidenceArtifact, and DecisionNote spine so completed backtests auto-capture durable evidence, decisions remain explicit, and Omnisearch recalls typed artifacts without regressing P0 continuity.

**Architecture:** Keep `backtest_runs` as the immutable internal Run truth and add a small additive object spine around it. Put evidence creation and decision mutation in focused domain/service modules, keep `agent.py` as wiring only, keep user-facing copy in i18n/presentation layers, and make frontend Omnisearch consume typed backend search payloads instead of filtering to conversations.

**Tech Stack:** FastAPI, Pydantic, Supabase/Postgres migrations with RLS, pytest, Next.js/React, TypeScript, i18next, Bun tests, Codex browser QA.

---

## Source Of Truth

- Mandatory canon docs: `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`, `.agent/designs/argus/DESIGN.md`.
- Active roadmap: `docs/specs/private-alpha-next-roadmap.md`.
- P1 strategic detail: `docs/specs/private-alpha-next-decision-memo.md`, especially sections `15.1` and `15.2`.
- Release discipline: `docs/specs/private-alpha-ci-cd-sota.md`, `docs/PRIVATE_LAUNCH_RUNBOOK.md`, `docs/release-manifests/TEMPLATE.md`.
- Current branch: `codex/private-alpha-next-reintegration`.

## P1 Anti-Drift Rules

- Do not add regex, localized phrase gates, or language-specific semantic routing.
- Do not use translated labels as state. Use typed codes and localize only at presentation.
- Do not put new product behavior in `llm_interpreter.py` or expand interpreter branches for action state.
- Do not make `save_strategy` the P1 commitment action. It can remain compatibility for the existing Strategies feature flag only.
- Do not create a standalone ledger dashboard. Omnisearch is the first recall wedge.
- Do not make Recents an append-only artifact feed. Recents remains chat navigation.
- Do not add `EvidenceArtifact` or `DecisionNote` to `TaskSnapshot`, runtime artifact anchor precedence, retry supersession, or reload recovery in this slice. P1 objects are sidecars to completed run truth until a later hydration contract explicitly promotes them into runtime anchors.
- Do not expose raw `conversation_result_card`, context packets, route receipts, provider/model metadata, retry payloads, conversation transcripts, or private memory in Omnisearch previews or any artifact snapshot intended for broader reuse. P1 preview payloads must be sanitized owner-only digests.
- Do not add RAG, vector memory, broker/export, public excerpts, voice/STT, PostHog runtime integration, or live analytics dashboards.
- Do not broad cherry-pick from quarantine. Quarantine is reference only.
- Stop if a UI surface needs to invent facts, digest text, decision state, or artifact lifecycle not returned by the backend.
- Stop if typed search can return a new object but cannot preview/open it as a typed object without falling back to raw run blobs.
- Stop if the change cannot be reverted as one coherent P1 commit or a short series of coherent P1 commits.

## File Structure

### Backend Domain And Persistence

- Create `src/argus/domain/evidence.py`
  - Defines lifecycle and decision literals.
  - Builds deterministic Idea/IdeaVersion/EvidenceArtifact/DecisionNote model objects.
  - Builds evidence digests from canonical run/card fields.
  - Builds a sanitized preview payload that excludes raw context packets, route receipts, provider/model metadata, retry payloads, transcripts, and public/export-only fields.
  - Contains no localized prose and no user-facing label selection.
- Modify `src/argus/api/schemas.py`
  - Adds Pydantic models for `Idea`, `IdeaVersion`, `EvidenceArtifact`, `DecisionNote`, decision request/response, and typed search item metadata.
  - Extends `SearchItem.type` to include `idea`, `backtest`, `evidence`, and `decision`.
  - Extends `ChatActionType` with `add_decision` only if card action transport needs it; the primary decision path should be a REST endpoint.
- Modify `src/argus/domain/store.py`
  - Adds in-memory maps for ideas, idea versions, evidence artifacts, decision notes, and ownership maps.
- Modify `src/argus/domain/supabase_gateway.py`
  - Adds owner-checked inserts/upserts/selects for new P1 tables.
  - Extends search rows to include typed P1 objects.
- Create `src/argus/api/chat/evidence.py`
  - Orchestrates auto-capture after completed backtest persistence.
  - Adds idempotency by `source_run_id`.
  - Adds decision capture helper by evidence artifact id.
- Create `src/argus/api/routers/evidence.py`
  - Adds `POST /api/v1/evidence-artifacts/{artifact_id}/decision`.
  - Optionally adds `GET /api/v1/evidence-artifacts/{artifact_id}` if needed for typed Omnisearch preview.
- Modify `src/argus/api/main.py`
  - Registers the evidence router.
- Modify `src/argus/api/chat/persistence.py`
  - Calls evidence auto-capture after a run is stored in memory/Supabase.
  - Enriches result card payloads with `evidence_artifact_id`, `idea_id`, and `idea_version_id`.
  - Does not write these ids into runtime anchor precedence or retry metadata.
- Modify `src/argus/api/routers/search.py`
  - Maps typed rows to `SearchItem` without hiding product artifacts.
- Modify `src/argus/api/search_utils.py`
  - Updates result type ranking so `decision`, `evidence`, `backtest`, and `idea` rank coherently with conversations.

### Database

- Create `supabase/migrations/20260619000001_p1_evidence_decision_spine.sql`
  - Additive tables: `ideas`, `idea_versions`, `evidence_artifacts`, `decision_notes`.
  - RLS enabled on each table.
  - Owner policy by `user_id = auth.uid()`.
  - Indexes by owner, source run, lifecycle, decision state, and recency.
  - No destructive changes to `backtest_runs` or `strategies`.

### Frontend

- Modify `web/lib/argus-api.ts`
  - Adds P1 types and decision API client.
  - Extends `SearchItem` for typed object metadata and preview digest.
- Modify `web/components/chat/types.ts`
  - Adds `add_decision` action type only if transported in card actions.
  - Adds evidence ids and decision metadata to result card types if needed.
- Modify `web/lib/chat-result-actions.ts`
  - Allows `add_decision` action only when backend provides artifact identity.
- Modify `web/components/chat/StrategyResultCard.tsx`
  - Adds a compact decision capture rail tied to `evidence_artifact_id`.
  - Keeps decision chips neutral at rest, semantic on hover/focus/selected only.
  - Uses i18next keys only for labels.
- Create `web/lib/command-palette-items.ts`
  - Pure adapter from backend `SearchItem`/`HistoryItem` to display items.
  - Preserves typed non-chat objects instead of filtering them out.
- Modify `web/components/sidebar/ChatCommandPalette.tsx`
  - Uses the pure adapter.
  - Shows type pills for Conversation, Backtest, Evidence, Decision, Idea.
  - Shows grounded preview digest from backend payload.
  - Keeps a single footer navigation action for source conversation/open destination.
- Modify `web/public/locales/en/common.json` and `web/public/locales/es-419/common.json`
  - Adds labels for decision states, type pills, preview headings, and decision form actions.

### Docs And Tests

- Modify `docs/API_CONTRACT.md`
  - Documents P1 object contract, decision endpoint, search item types, lifecycle labels, and result card metadata.
- Modify `docs/DATA_MODEL.md`
  - Documents new tables, RLS, immutability, lifecycle mutability, and relationships.
- Modify `docs/api/openapi.yaml`
  - Adds P1 schemas and endpoint.
- Modify `docs/specs/private-alpha-next-roadmap.md`
  - Marks P1 checkboxes as completed only after tests and browser QA pass.
- Create `tests/test_p1_evidence_spine.py`
  - Domain and in-memory API tests for auto-capture and idempotency.
- Extend `tests/test_supabase_gateway.py`
  - Persistence payload/RLS ownership tests for new tables.
- Extend `tests/test_alpha_api.py` and `tests/test_alpha_api_supabase.py`
  - Decision endpoint and typed search tests.
- Extend `tests/test_chat_stream_contract.py`
  - Result final payload includes evidence ids and no duplicate card state.
- Extend `web/__tests__/chat-result-actions.test.ts`
  - Decision action hydration and visibility.
- Create `web/__tests__/command-palette-items.test.ts`
  - Typed Omnisearch adapter tests.
- Extend `web/__tests__/alpha-frontend.test.ts`
  - Static guard that command palette no longer filters search results to chat only.

## Implementation Tasks

### Task 1: Contract Docs And Failing Backend Tests

**Files:**
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/api/openapi.yaml`
- Create: `tests/test_p1_evidence_spine.py`
- Modify: `tests/test_supabase_gateway.py`
- Modify: `tests/test_alpha_api.py`
- Modify: `tests/test_alpha_api_supabase.py`

- [ ] **Step 1: Update `docs/DATA_MODEL.md` with exact P1 tables**

Add a section after `backtest_runs` describing:

```markdown
## 12.2 ideas

User-owned root for an investing thesis or question. Ideas are automatically
created from completed evidence as `captured`; they are not user-endorsed until
an explicit save, pin, or decision action changes lifecycle.

Fields:
- `id`: uuid primary key
- `user_id`: uuid references `profiles.id`
- `source_conversation_id`: uuid nullable references `conversations.id`
- `title`: text
- `summary`: text
- `lifecycle`: text check in `captured`, `reviewed`, `saved`, `decided`, `archived`, `discarded`
- `active_version_id`: uuid nullable
- `created_at`: timestamptz
- `updated_at`: timestamptz

Immutable truth lives in `idea_versions` and `evidence_artifacts`; lifecycle and
active version pointers are mutable.
```

Then add matching `idea_versions`, `evidence_artifacts`, and `decision_notes` subsections:

```markdown
## 12.3 idea_versions

Immutable canonical snapshot of one idea state.

Fields:
- `id`, `user_id`, `idea_id`, `source_conversation_id`, `source_run_id`
- `version_number`: integer
- `canonical_spec`: jsonb
- `strategy_snapshot`: jsonb
- `title`: text
- `summary`: text
- `lifecycle`: text
- `created_at`: timestamptz

## 12.4 evidence_artifacts

Immutable human-readable proof object generated from a run/result/research
source. P1 creates `artifact_type = backtest` from completed backtests.

Fields:
- `id`, `user_id`, `idea_id`, `idea_version_id`, `source_conversation_id`, `source_run_id`
- `artifact_type`: text, initially `backtest`
- `lifecycle`: text
- `title`: text
- `digest`: text
- `payload`: jsonb with assumptions, metrics, quick take, result card, chart summary, provenance
- `created_at`: timestamptz
- `updated_at`: timestamptz

## 12.5 decision_notes

Explicit user judgment attached to an evidence artifact.

Fields:
- `id`, `user_id`, `idea_id`, `idea_version_id`, `evidence_artifact_id`, `source_conversation_id`
- `decision_state`: text check in `watching`, `promising`, `rejected`, `revisit_later`
- `note`: text nullable
- `created_at`: timestamptz
- `updated_at`: timestamptz
```

- [ ] **Step 2: Update `docs/API_CONTRACT.md` with typed P1 API**

Add:

```markdown
### Evidence Artifacts

`POST /api/v1/evidence-artifacts/{artifact_id}/decision`

Request:
{
  "decision_state": "watching",
  "note": "Revisit after next earnings."
}

Response:
{
  "decision": {
    "id": "uuid",
    "evidence_artifact_id": "uuid",
    "idea_id": "uuid",
    "idea_version_id": "uuid",
    "decision_state": "watching",
    "note": "Revisit after next earnings.",
    "created_at": "timestamp",
    "updated_at": "timestamp"
  },
  "evidence_artifact": {
    "id": "uuid",
    "artifact_type": "backtest",
    "lifecycle": "decided"
  }
}
```

Document search types:

```markdown
SearchItem.type values:
- `chat`: conversation
- `backtest`: completed historical simulation read model backed by `backtest_runs`
- `evidence`: evidence artifact
- `decision`: decision note
- `idea`: idea root
- `strategy` and `collection`: compatibility surfaces while flags exist
```

- [ ] **Step 3: Add failing domain/API tests**

Create `tests/test_p1_evidence_spine.py` with:

```python
from __future__ import annotations

from argus.api import state as api_state
from argus.api.schemas import BacktestRun, Conversation, User
from argus.domain.store import utcnow


def _user() -> User:
    return User(
        id="user-1",
        email="user@example.com",
        username=None,
        display_name=None,
        language="en",
        locale="en-US",
        theme="dark",
        is_admin=False,
        created_at=utcnow(),
        updated_at=utcnow(),
    )


def _conversation() -> Conversation:
    return Conversation(
        id="conv-1",
        title="AAPL MSFT TSLA idea",
        title_source="system_default",
        created_at=utcnow(),
        updated_at=utcnow(),
        last_message_preview="AAPL MSFT TSLA buy and hold",
    )


def _run() -> BacktestRun:
    return BacktestRun(
        id="run-1",
        conversation_id="conv-1",
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL", "MSFT", "TSLA"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 12.3}}, "by_symbol": {}},
        config_snapshot={
            "template": "buy_and_hold",
            "symbols": ["AAPL", "MSFT", "TSLA"],
            "benchmark_symbol": "SPY",
            "date_range": {"start": "2023-01-01", "end": "2026-06-19"},
        },
        conversation_result_card={
            "title": "AAPL, MSFT, TSLA Buy and Hold",
            "status_label": "Simulation Complete",
            "rows": [{"key": "total_return_pct", "label": "Total Return", "value": "+12.3%"}],
            "assumptions": ["Benchmark: SPY", "No fees"],
            "actions": [],
        },
        created_at=utcnow(),
        chart=None,
        trades=[],
    )


def test_completed_backtest_auto_captures_idea_version_and_evidence() -> None:
    from argus.api.chat.evidence import auto_capture_completed_backtest

    api_state.store.reset()
    user = _user()
    conversation = _conversation()
    run = _run()
    api_state.store.users[user.id] = user
    api_state.store.conversations[conversation.id] = conversation
    api_state.store.conversation_owners[conversation.id] = user.id
    api_state.store.backtest_runs[run.id] = run
    api_state.store.backtest_run_owners[run.id] = user.id

    captured = auto_capture_completed_backtest(
        user=user,
        conversation=conversation,
        run=run,
    )

    assert captured.idea.lifecycle == "captured"
    assert captured.idea_version.idea_id == captured.idea.id
    assert captured.evidence_artifact.idea_version_id == captured.idea_version.id
    assert captured.evidence_artifact.artifact_type == "backtest"
    assert captured.evidence_artifact.source_run_id == run.id
    assert captured.evidence_artifact.digest
    assert run.conversation_result_card["evidence_artifact_id"] == captured.evidence_artifact.id
    assert run.conversation_result_card["idea_id"] == captured.idea.id
    assert run.conversation_result_card["idea_version_id"] == captured.idea_version.id


def test_completed_backtest_capture_is_idempotent_by_run_id() -> None:
    from argus.api.chat.evidence import auto_capture_completed_backtest

    api_state.store.reset()
    user = _user()
    conversation = _conversation()
    run = _run()
    api_state.store.conversations[conversation.id] = conversation
    api_state.store.conversation_owners[conversation.id] = user.id
    api_state.store.backtest_runs[run.id] = run
    api_state.store.backtest_run_owners[run.id] = user.id

    first = auto_capture_completed_backtest(user=user, conversation=conversation, run=run)
    second = auto_capture_completed_backtest(user=user, conversation=conversation, run=run)

    assert second.idea.id == first.idea.id
    assert second.idea_version.id == first.idea_version.id
    assert second.evidence_artifact.id == first.evidence_artifact.id
    assert len(api_state.store.evidence_artifacts) == 1
```

- [ ] **Step 4: Run failing backend tests**

Run:

```bash
poetry run pytest tests/test_p1_evidence_spine.py -q
```

Expected: FAIL because `argus.api.chat.evidence` or store attributes do not exist.

- [ ] **Step 5: Add failing search and decision API tests**

Append to `tests/test_alpha_api.py`:

```python
def test_decision_endpoint_marks_evidence_artifact_decided() -> None:
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        headers={"Idempotency-Key": "chat-p1-evidence"},
        json={
            "conversation_id": conversation["id"],
            "message": "Backtest TSLA from 2025 to 2025",
            "language": "en",
        },
    )
    payload = _final_payload(response.text)
    artifact_id = payload["run"]["conversation_result_card"]["evidence_artifact_id"]

    decision = client.post(
        f"/api/v1/evidence-artifacts/{artifact_id}/decision",
        json={"decision_state": "promising", "note": "Worth revisiting."},
    )

    assert decision.status_code == 200
    body = decision.json()
    assert body["decision"]["decision_state"] == "promising"
    assert body["decision"]["note"] == "Worth revisiting."
    assert body["evidence_artifact"]["lifecycle"] == "decided"


def test_search_returns_typed_p1_artifacts() -> None:
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        headers={"Idempotency-Key": "chat-p1-search"},
        json={
            "conversation_id": conversation["id"],
            "message": "Backtest TSLA from 2025 to 2025",
            "language": "en",
        },
    )
    artifact_id = _final_payload(response.text)["run"]["conversation_result_card"]["evidence_artifact_id"]
    client.post(
        f"/api/v1/evidence-artifacts/{artifact_id}/decision",
        json={"decision_state": "watching", "note": "Track it."},
    )

    payload = client.get("/api/v1/search?q=TSLA&limit=20").json()

    types = {item["type"] for item in payload["items"]}
    assert {"chat", "backtest", "evidence", "idea", "decision"}.issubset(types)
    evidence = next(item for item in payload["items"] if item["type"] == "evidence")
    assert evidence["conversation_id"] == conversation["id"]
    assert evidence["preview"]["digest"]
```

Run:

```bash
poetry run pytest tests/test_alpha_api.py::test_decision_endpoint_marks_evidence_artifact_decided tests/test_alpha_api.py::test_search_returns_typed_p1_artifacts -q
```

Expected: FAIL because endpoint and search fields do not exist.

- [ ] **Step 6: Commit contract/test red state only if desired**

If keeping red tests in a separate checkpoint:

```bash
git add docs/API_CONTRACT.md docs/DATA_MODEL.md docs/api/openapi.yaml tests/test_p1_evidence_spine.py tests/test_alpha_api.py tests/test_alpha_api_supabase.py tests/test_supabase_gateway.py
git commit -m "test(p1): define evidence decision contract"
```

Expected: commit succeeds only if the team wants an explicit red-test checkpoint. Otherwise keep uncommitted and continue to Task 2.

### Task 2: Add P1 Domain Models, Store, Migration, And Supabase Gateway

**Files:**
- Create: `src/argus/domain/evidence.py`
- Modify: `src/argus/api/schemas.py`
- Modify: `src/argus/domain/store.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Create: `supabase/migrations/20260619000001_p1_evidence_decision_spine.sql`
- Modify: `tests/test_supabase_gateway.py`
- Test: `tests/test_p1_evidence_spine.py`, `tests/test_supabase_gateway.py`

- [ ] **Step 1: Add schema models**

In `src/argus/api/schemas.py`, add literals near the existing type aliases:

```python
ArtifactLifecycle = Literal[
    "captured",
    "reviewed",
    "saved",
    "decided",
    "archived",
    "discarded",
]
EvidenceArtifactType = Literal["backtest"]
DecisionState = Literal["watching", "promising", "rejected", "revisit_later"]
```

Add models after `BacktestJobResponse`:

```python
class Idea(BaseModel):
    id: str
    source_conversation_id: str | None = None
    title: str
    summary: str
    lifecycle: ArtifactLifecycle = "captured"
    active_version_id: str | None = None
    created_at: datetime
    updated_at: datetime


class IdeaVersion(BaseModel):
    id: str
    idea_id: str
    source_conversation_id: str | None = None
    source_run_id: str | None = None
    version_number: int = 1
    canonical_spec: dict[str, Any]
    strategy_snapshot: dict[str, Any]
    title: str
    summary: str
    lifecycle: ArtifactLifecycle = "captured"
    created_at: datetime


class EvidenceArtifact(BaseModel):
    id: str
    idea_id: str
    idea_version_id: str
    source_conversation_id: str | None = None
    source_run_id: str | None = None
    artifact_type: EvidenceArtifactType = "backtest"
    lifecycle: ArtifactLifecycle = "captured"
    title: str
    digest: str
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class DecisionNote(BaseModel):
    id: str
    idea_id: str
    idea_version_id: str
    evidence_artifact_id: str
    source_conversation_id: str | None = None
    decision_state: DecisionState
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class DecisionNoteCreate(BaseModel):
    decision_state: DecisionState
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class DecisionNoteResponse(BaseModel):
    decision: DecisionNote
    evidence_artifact: EvidenceArtifact
```

Extend `SearchItem`:

```python
class SearchItem(BaseModel):
    type: Literal[
        "chat",
        "strategy",
        "collection",
        "run",
        "backtest",
        "evidence",
        "decision",
        "idea",
    ]
    id: str
    title: str
    matched_text: str
    updated_at: datetime
    conversation_id: str | None = None
    lifecycle: ArtifactLifecycle | None = None
    preview: dict[str, Any] | None = None
```

- [ ] **Step 2: Extend in-memory store**

In `src/argus/domain/store.py`, import the new models and add fields:

```python
from argus.api.schemas import (
    Collection,
    Conversation,
    DecisionNote,
    EvidenceArtifact,
    Idea,
    IdeaVersion,
    Message,
    OnboardingState,
    Strategy,
    User,
)
```

Add to `AlphaStore`:

```python
ideas: dict[str, Idea] = field(default_factory=dict)
idea_owners: dict[str, str] = field(default_factory=dict)
idea_versions: dict[str, IdeaVersion] = field(default_factory=dict)
idea_version_owners: dict[str, str] = field(default_factory=dict)
evidence_artifacts: dict[str, EvidenceArtifact] = field(default_factory=dict)
evidence_artifact_owners: dict[str, str] = field(default_factory=dict)
decision_notes: dict[str, DecisionNote] = field(default_factory=dict)
decision_note_owners: dict[str, str] = field(default_factory=dict)
```

Clear them in `reset()`.

- [ ] **Step 3: Create deterministic domain builder**

Create `src/argus/domain/evidence.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from argus.api.schemas import BacktestRun, DecisionNote, EvidenceArtifact, Idea, IdeaVersion


@dataclass(frozen=True)
class CapturedEvidence:
    idea: Idea
    idea_version: IdeaVersion
    evidence_artifact: EvidenceArtifact


def build_backtest_evidence_capture(
    *,
    run: BacktestRun,
    idea_id: str,
    idea_version_id: str,
    evidence_artifact_id: str,
    now: datetime,
) -> CapturedEvidence:
    title = _title_from_run(run)
    digest = evidence_digest_from_run(run)
    idea = Idea(
        id=idea_id,
        source_conversation_id=run.conversation_id,
        title=title,
        summary=digest,
        lifecycle="captured",
        active_version_id=idea_version_id,
        created_at=now,
        updated_at=now,
    )
    idea_version = IdeaVersion(
        id=idea_version_id,
        idea_id=idea_id,
        source_conversation_id=run.conversation_id,
        source_run_id=run.id,
        version_number=1,
        canonical_spec=_canonical_spec_from_run(run),
        strategy_snapshot=dict(run.config_snapshot),
        title=title,
        summary=digest,
        lifecycle="captured",
        created_at=now,
    )
    evidence_artifact = EvidenceArtifact(
        id=evidence_artifact_id,
        idea_id=idea_id,
        idea_version_id=idea_version_id,
        source_conversation_id=run.conversation_id,
        source_run_id=run.id,
        artifact_type="backtest",
        lifecycle="captured",
        title=title,
        digest=digest,
        payload=_payload_from_run(run, digest=digest),
        created_at=now,
        updated_at=now,
    )
    return CapturedEvidence(
        idea=idea,
        idea_version=idea_version,
        evidence_artifact=evidence_artifact,
    )


def build_decision_note(
    *,
    evidence_artifact: EvidenceArtifact,
    decision_id: str,
    decision_state: str,
    note: str | None,
    now: datetime,
) -> DecisionNote:
    return DecisionNote(
        id=decision_id,
        idea_id=evidence_artifact.idea_id,
        idea_version_id=evidence_artifact.idea_version_id,
        evidence_artifact_id=evidence_artifact.id,
        source_conversation_id=evidence_artifact.source_conversation_id,
        decision_state=decision_state,  # validated by Pydantic caller
        note=note,
        created_at=now,
        updated_at=now,
    )


def evidence_digest_from_run(run: BacktestRun) -> str:
    card = run.conversation_result_card if isinstance(run.conversation_result_card, dict) else {}
    row_text = " ".join(
        str(row.get("value") or "")
        for row in card.get("rows", [])
        if isinstance(row, dict)
    ).strip()
    symbols = ", ".join(run.symbols)
    benchmark = run.benchmark_symbol
    if row_text:
        return f"{symbols} backtest versus {benchmark}. {row_text}"
    return f"{symbols} backtest versus {benchmark}."


def _title_from_run(run: BacktestRun) -> str:
    card = run.conversation_result_card if isinstance(run.conversation_result_card, dict) else {}
    title = card.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return f"{', '.join(run.symbols)} Backtest"


def _canonical_spec_from_run(run: BacktestRun) -> dict[str, Any]:
    return {
        "asset_class": run.asset_class,
        "symbols": list(run.symbols),
        "allocation_method": run.allocation_method,
        "benchmark_symbol": run.benchmark_symbol,
        "config_snapshot": dict(run.config_snapshot),
    }


def _payload_from_run(run: BacktestRun, *, digest: str) -> dict[str, Any]:
    card = run.conversation_result_card if isinstance(run.conversation_result_card, dict) else {}
    safe_card = {
        key: card.get(key)
        for key in (
            "title",
            "symbols",
            "strategy_label",
            "asset_class",
            "date_range",
            "status_label",
            "rows",
            "benchmark_note",
            "assumptions",
        )
        if key in card
    }
    return {
        "artifact_type": "backtest",
        "digest": digest,
        "source": {
            "run_id": run.id,
            "conversation_id": run.conversation_id,
            "strategy_id": run.strategy_id,
        },
        "assumptions": list(card.get("assumptions") or []),
        "metrics": run.metrics,
        "result_card": safe_card,
        "chart_summary": _chart_summary(run.chart),
        "provenance": {
            "asset_class": run.asset_class,
            "symbols": list(run.symbols),
            "benchmark_symbol": run.benchmark_symbol,
            "created_at": run.created_at.isoformat(),
        },
    }


def _chart_summary(chart: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(chart, dict):
        return None
    series = chart.get("series")
    return {
        "kind": chart.get("kind"),
        "points": len(series) if isinstance(series, list) else 0,
        "currency": chart.get("currency"),
        "value_summary": chart.get("value_summary"),
    }
```

- [ ] **Step 4: Add additive migration**

Create `supabase/migrations/20260619000001_p1_evidence_decision_spine.sql`:

```sql
create table if not exists public.ideas (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  source_conversation_id uuid references public.conversations(id) on delete set null,
  title text not null,
  summary text not null default '',
  lifecycle text not null default 'captured' check (lifecycle in ('captured', 'reviewed', 'saved', 'decided', 'archived', 'discarded')),
  active_version_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.idea_versions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  idea_id uuid not null references public.ideas(id) on delete cascade,
  source_conversation_id uuid references public.conversations(id) on delete set null,
  source_run_id uuid references public.backtest_runs(id) on delete set null,
  version_number integer not null default 1,
  canonical_spec jsonb not null default '{}'::jsonb,
  strategy_snapshot jsonb not null default '{}'::jsonb,
  title text not null,
  summary text not null default '',
  lifecycle text not null default 'captured' check (lifecycle in ('captured', 'reviewed', 'saved', 'decided', 'archived', 'discarded')),
  created_at timestamptz not null default now(),
  unique(user_id, idea_id, version_number)
);

alter table public.ideas
  add constraint ideas_active_version_id_fkey
  foreign key (active_version_id) references public.idea_versions(id) on delete set null;

create table if not exists public.evidence_artifacts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  idea_id uuid not null references public.ideas(id) on delete cascade,
  idea_version_id uuid not null references public.idea_versions(id) on delete cascade,
  source_conversation_id uuid references public.conversations(id) on delete set null,
  source_run_id uuid references public.backtest_runs(id) on delete set null,
  artifact_type text not null default 'backtest' check (artifact_type in ('backtest')),
  lifecycle text not null default 'captured' check (lifecycle in ('captured', 'reviewed', 'saved', 'decided', 'archived', 'discarded')),
  title text not null,
  digest text not null default '',
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, source_run_id)
);

create table if not exists public.decision_notes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  idea_id uuid not null references public.ideas(id) on delete cascade,
  idea_version_id uuid not null references public.idea_versions(id) on delete cascade,
  evidence_artifact_id uuid not null references public.evidence_artifacts(id) on delete cascade,
  source_conversation_id uuid references public.conversations(id) on delete set null,
  decision_state text not null check (decision_state in ('watching', 'promising', 'rejected', 'revisit_later')),
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_ideas_user_updated on public.ideas(user_id, updated_at desc);
create index if not exists idx_ideas_user_lifecycle on public.ideas(user_id, lifecycle);
create index if not exists idx_idea_versions_user_idea on public.idea_versions(user_id, idea_id, created_at desc);
create index if not exists idx_evidence_artifacts_user_updated on public.evidence_artifacts(user_id, updated_at desc);
create index if not exists idx_evidence_artifacts_source_run on public.evidence_artifacts(user_id, source_run_id);
create index if not exists idx_decision_notes_user_updated on public.decision_notes(user_id, updated_at desc);
create index if not exists idx_decision_notes_artifact on public.decision_notes(user_id, evidence_artifact_id);
create index if not exists idx_decision_notes_state on public.decision_notes(user_id, decision_state);

drop trigger if exists set_ideas_updated_at on public.ideas;
create trigger set_ideas_updated_at
before update on public.ideas
for each row execute function public.set_updated_at();

drop trigger if exists set_evidence_artifacts_updated_at on public.evidence_artifacts;
create trigger set_evidence_artifacts_updated_at
before update on public.evidence_artifacts
for each row execute function public.set_updated_at();

drop trigger if exists set_decision_notes_updated_at on public.decision_notes;
create trigger set_decision_notes_updated_at
before update on public.decision_notes
for each row execute function public.set_updated_at();

alter table public.ideas enable row level security;
alter table public.idea_versions enable row level security;
alter table public.evidence_artifacts enable row level security;
alter table public.decision_notes enable row level security;

drop policy if exists ideas_owner_all on public.ideas;
create policy ideas_owner_all on public.ideas for all using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists idea_versions_owner_all on public.idea_versions;
create policy idea_versions_owner_all on public.idea_versions for all using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists evidence_artifacts_owner_all on public.evidence_artifacts;
create policy evidence_artifacts_owner_all on public.evidence_artifacts for all using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists decision_notes_owner_all on public.decision_notes;
create policy decision_notes_owner_all on public.decision_notes for all using (user_id = auth.uid()) with check (user_id = auth.uid());
```

- [ ] **Step 5: Add Supabase gateway methods**

In `src/argus/domain/supabase_gateway.py`, add:

```python
    def create_idea(self, *, user_id: str, idea: Idea) -> Idea:
        self._require_owned_conversation(
            user_id=user_id,
            conversation_id=idea.source_conversation_id,
        )
        payload = idea.model_dump(mode="json")
        payload["user_id"] = user_id
        created = self.client.table("ideas").insert(payload).execute()
        return Idea.model_validate(_row_one(created))

    def create_idea_version(self, *, user_id: str, version: IdeaVersion) -> IdeaVersion:
        self._require_owned_idea(user_id=user_id, idea_id=version.idea_id)
        self._require_owned_conversation(
            user_id=user_id,
            conversation_id=version.source_conversation_id,
        )
        self._require_owned_backtest_run(user_id=user_id, run_id=version.source_run_id)
        payload = version.model_dump(mode="json")
        payload["user_id"] = user_id
        created = self.client.table("idea_versions").insert(payload).execute()
        return IdeaVersion.model_validate(_row_one(created))

    def create_evidence_artifact(
        self, *, user_id: str, artifact: EvidenceArtifact
    ) -> EvidenceArtifact:
        self._require_owned_idea(user_id=user_id, idea_id=artifact.idea_id)
        self._require_owned_idea_version(
            user_id=user_id,
            idea_version_id=artifact.idea_version_id,
        )
        self._require_owned_conversation(
            user_id=user_id,
            conversation_id=artifact.source_conversation_id,
        )
        self._require_owned_backtest_run(
            user_id=user_id,
            run_id=artifact.source_run_id,
        )
        payload = artifact.model_dump(mode="json")
        payload["user_id"] = user_id
        created = self.client.table("evidence_artifacts").insert(payload).execute()
        return EvidenceArtifact.model_validate(_row_one(created))
```

Also add `get_evidence_artifact`, `create_decision_note`, and owner helpers:

```python
    def _require_owned_idea(self, *, user_id: str, idea_id: str | None) -> None:
        if idea_id is None:
            return
        result = self.client.table("ideas").select("id").eq("user_id", user_id).eq("id", idea_id).limit(1).execute()
        if _row_one(result) is None:
            raise ValueError("Idea not found or not owned by user.")

    def _require_owned_idea_version(
        self, *, user_id: str, idea_version_id: str | None
    ) -> None:
        if idea_version_id is None:
            return
        result = self.client.table("idea_versions").select("id").eq("user_id", user_id).eq("id", idea_version_id).limit(1).execute()
        if _row_one(result) is None:
            raise ValueError("Idea version not found or not owned by user.")

    def _require_owned_backtest_run(self, *, user_id: str, run_id: str | None) -> None:
        if run_id is None:
            return
        result = self.client.table("backtest_runs").select("id").eq("user_id", user_id).eq("id", run_id).limit(1).execute()
        if _row_one(result) is None:
            raise ValueError("Backtest run not found or not owned by user.")
```

- [ ] **Step 6: Run tests**

Run:

```bash
poetry run pytest tests/test_p1_evidence_spine.py tests/test_supabase_gateway.py -q
```

Expected: P1 domain tests may still fail until Task 3 wires persistence; Supabase gateway tests for model/payload ownership should pass after gateway work is complete.

### Task 3: Wire Auto-Capture Into Backtest Persistence

**Files:**
- Create/Modify: `src/argus/api/chat/evidence.py`
- Modify: `src/argus/api/chat/persistence.py`
- Modify: `src/argus/api/routers/agent.py`
- Test: `tests/test_p1_evidence_spine.py`, `tests/test_chat_stream_contract.py`, `tests/test_alpha_api.py`

- [ ] **Step 1: Implement auto-capture service**

Create `src/argus/api/chat/evidence.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import dev_memory_fallback_enabled
from argus.api.schemas import (
    BacktestRun,
    Conversation,
    DecisionNote,
    DecisionNoteCreate,
    EvidenceArtifact,
    User,
)
from argus.domain.evidence import (
    CapturedEvidence,
    build_backtest_evidence_capture,
    build_decision_note,
)
from argus.domain.store import utcnow


def auto_capture_completed_backtest(
    *,
    user: User,
    conversation: Conversation,
    run: BacktestRun,
) -> CapturedEvidence:
    existing = _existing_capture_for_run(user_id=user.id, run_id=run.id)
    if existing is not None:
        _attach_capture_to_result_card(run=run, captured=existing)
        return existing

    now = utcnow()
    captured = build_backtest_evidence_capture(
        run=run,
        idea_id=api_state.store.new_id(),
        idea_version_id=api_state.store.new_id(),
        evidence_artifact_id=api_state.store.new_id(),
        now=now,
    )

    _store_capture_in_memory(user_id=user.id, captured=captured)
    if api_state.supabase_gateway is not None:
        try:
            idea = api_state.supabase_gateway.create_idea(
                user_id=user.id,
                idea=captured.idea,
            )
            version = api_state.supabase_gateway.create_idea_version(
                user_id=user.id,
                version=captured.idea_version,
            )
            artifact = api_state.supabase_gateway.create_evidence_artifact(
                user_id=user.id,
                artifact=captured.evidence_artifact,
            )
            captured = CapturedEvidence(
                idea=idea,
                idea_version=version,
                evidence_artifact=artifact,
            )
            _store_capture_in_memory(user_id=user.id, captured=captured)
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase evidence capture failed; using dev memory fallback",
                error=str(exc),
                run_id=run.id,
            )

    _attach_capture_to_result_card(run=run, captured=captured)
    return captured
```

Add helper functions:

```python
def _existing_capture_for_run(*, user_id: str, run_id: str) -> CapturedEvidence | None:
    for artifact in api_state.store.evidence_artifacts.values():
        if (
            artifact.source_run_id == run_id
            and api_state.store.evidence_artifact_owners.get(artifact.id) == user_id
        ):
            idea = api_state.store.ideas.get(artifact.idea_id)
            version = api_state.store.idea_versions.get(artifact.idea_version_id)
            if idea is not None and version is not None:
                return CapturedEvidence(
                    idea=idea,
                    idea_version=version,
                    evidence_artifact=artifact,
                )
    return None


def _store_capture_in_memory(*, user_id: str, captured: CapturedEvidence) -> None:
    api_state.store.ideas[captured.idea.id] = captured.idea
    api_state.store.idea_owners[captured.idea.id] = user_id
    api_state.store.idea_versions[captured.idea_version.id] = captured.idea_version
    api_state.store.idea_version_owners[captured.idea_version.id] = user_id
    api_state.store.evidence_artifacts[captured.evidence_artifact.id] = captured.evidence_artifact
    api_state.store.evidence_artifact_owners[captured.evidence_artifact.id] = user_id


def _attach_capture_to_result_card(*, run: BacktestRun, captured: CapturedEvidence) -> None:
    card = dict(run.conversation_result_card)
    card["idea_id"] = captured.idea.id
    card["idea_version_id"] = captured.idea_version.id
    card["evidence_artifact_id"] = captured.evidence_artifact.id
    card["evidence_lifecycle"] = captured.evidence_artifact.lifecycle
    card["artifact_type"] = "backtest"
    actions = card.get("actions")
    if isinstance(actions, list):
        enriched_actions = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            payload = dict(action.get("payload") or {})
            payload.update(
                {
                    "idea_id": captured.idea.id,
                    "idea_version_id": captured.idea_version.id,
                    "evidence_artifact_id": captured.evidence_artifact.id,
                }
            )
            enriched_actions.append({**action, "payload": payload})
        card["actions"] = enriched_actions
    run.conversation_result_card = card
```

- [ ] **Step 2: Guard against runtime anchor drift**

Run this scan before and after implementation:

```bash
rg -n "EvidenceArtifact|DecisionNote|evidence_artifact_id|idea_version_id|idea_id" src/argus/agent_runtime src/argus/api/message_store.py src/argus/api/chat/recovery.py
```

Expected: no new evidence/decision ids appear in `TaskSnapshot`, `resolve_artifact_anchor`, `_AUTHORITATIVE_ARTIFACT_KEYS`, retry supersession, or reload recovery anchor precedence. Evidence ids may appear only in API message/result metadata and frontend rendering contracts.

- [ ] **Step 3: Call auto-capture in persistence**

In `src/argus/api/chat/persistence.py`, after the run is persisted and before return:

```python
    from argus.api.chat.evidence import auto_capture_completed_backtest

    try:
        auto_capture_completed_backtest(
            user=user,
            conversation=conversation,
            run=run,
        )
    except Exception as exc:
        if not dev_memory_fallback_enabled():
            raise
        logger.warning(
            "Evidence auto-capture failed; result run remains persisted",
            error=str(exc),
            run_id=run.id,
        )
```

- [ ] **Step 4: Add stream final assertions**

Append to `tests/test_chat_stream_contract.py`:

```python
def test_chat_stream_result_includes_evidence_artifact_identity() -> None:
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        headers={"Idempotency-Key": "chat-evidence-identity"},
        json={
            "conversation_id": conversation["id"],
            "message": "Backtest TSLA from 2025 to 2025",
            "language": "en",
        },
    )

    payload = _final_payload(response.text)
    card = payload["run"]["conversation_result_card"]
    assert card["artifact_type"] == "backtest"
    assert card["idea_id"]
    assert card["idea_version_id"]
    assert card["evidence_artifact_id"]
```

- [ ] **Step 5: Run tests**

Run:

```bash
poetry run pytest tests/test_p1_evidence_spine.py tests/test_chat_stream_contract.py::test_chat_stream_result_includes_evidence_artifact_identity -q
```

Expected: PASS.

### Task 4: Decision Capture API

**Files:**
- Modify: `src/argus/api/chat/evidence.py`
- Create: `src/argus/api/routers/evidence.py`
- Modify: `src/argus/api/main.py`
- Modify: `web/lib/argus-api.ts`
- Test: `tests/test_alpha_api.py`, `tests/test_alpha_api_supabase.py`

- [ ] **Step 1: Add decision service helper**

In `src/argus/api/chat/evidence.py`, add:

```python
def create_decision_for_evidence_artifact(
    *,
    user: User,
    artifact_id: str,
    payload: DecisionNoteCreate,
) -> tuple[DecisionNote, EvidenceArtifact]:
    artifact = _evidence_artifact_for_user(user_id=user.id, artifact_id=artifact_id)
    now = utcnow()
    decision = build_decision_note(
        evidence_artifact=artifact,
        decision_id=api_state.store.new_id(),
        decision_state=payload.decision_state,
        note=payload.note,
        now=now,
    )
    api_state.store.decision_notes[decision.id] = decision
    api_state.store.decision_note_owners[decision.id] = user.id

    artifact = artifact.model_copy(update={"lifecycle": "decided", "updated_at": now})
    api_state.store.evidence_artifacts[artifact.id] = artifact
    idea = api_state.store.ideas.get(artifact.idea_id)
    if idea is not None:
        api_state.store.ideas[idea.id] = idea.model_copy(
            update={"lifecycle": "decided", "updated_at": now}
        )

    if api_state.supabase_gateway is not None:
        decision = api_state.supabase_gateway.create_decision_note(
            user_id=user.id,
            decision=decision,
        )
        artifact = api_state.supabase_gateway.mark_evidence_artifact_lifecycle(
            user_id=user.id,
            artifact_id=artifact.id,
            lifecycle="decided",
        )
    return decision, artifact


def _evidence_artifact_for_user(*, user_id: str, artifact_id: str) -> EvidenceArtifact:
    artifact = api_state.store.evidence_artifacts.get(artifact_id)
    if (
        artifact is not None
        and api_state.store.evidence_artifact_owners.get(artifact_id) == user_id
    ):
        return artifact
    if api_state.supabase_gateway is not None:
        fetched = api_state.supabase_gateway.get_evidence_artifact(
            user_id=user_id,
            artifact_id=artifact_id,
        )
        if fetched is not None:
            api_state.store.evidence_artifacts[fetched.id] = fetched
            api_state.store.evidence_artifact_owners[fetched.id] = user_id
            return fetched
    raise ValueError("Evidence artifact not found or not owned by user.")
```

- [ ] **Step 2: Add router**

Create `src/argus/api/routers/evidence.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from argus.api.chat.evidence import create_decision_for_evidence_artifact
from argus.api.dependencies import current_user
from argus.api.schemas import DecisionNoteCreate, DecisionNoteResponse, User

router = APIRouter(prefix="/api/v1/evidence-artifacts", tags=["evidence"])


@router.post("/{artifact_id}/decision", response_model=DecisionNoteResponse)
def create_decision(
    artifact_id: str,
    payload: DecisionNoteCreate,
    user: User = Depends(current_user),  # noqa: B008
) -> DecisionNoteResponse:
    try:
        decision, artifact = create_decision_for_evidence_artifact(
            user=user,
            artifact_id=artifact_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DecisionNoteResponse(decision=decision, evidence_artifact=artifact)
```

Register in `src/argus/api/main.py`:

```python
from argus.api.routers import evidence

app.include_router(evidence.router)
```

- [ ] **Step 3: Add frontend API client**

In `web/lib/argus-api.ts`, add:

```ts
export type DecisionState = "watching" | "promising" | "rejected" | "revisit_later";

export type EvidenceArtifact = {
  id: string;
  idea_id: string;
  idea_version_id: string;
  source_conversation_id?: string | null;
  source_run_id?: string | null;
  artifact_type: "backtest";
  lifecycle: "captured" | "reviewed" | "saved" | "decided" | "archived" | "discarded";
  title: string;
  digest: string;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type DecisionNote = {
  id: string;
  idea_id: string;
  idea_version_id: string;
  evidence_artifact_id: string;
  source_conversation_id?: string | null;
  decision_state: DecisionState;
  note?: string | null;
  created_at: string;
  updated_at: string;
};

export async function createEvidenceDecision(
  artifactId: string,
  payload: { decision_state: DecisionState; note?: string | null },
) {
  return apiFetch<{ decision: DecisionNote; evidence_artifact: EvidenceArtifact }>(
    `/evidence-artifacts/${artifactId}/decision`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}
```

- [ ] **Step 4: Run decision API tests**

Run:

```bash
poetry run pytest tests/test_alpha_api.py::test_decision_endpoint_marks_evidence_artifact_decided -q
```

Expected: PASS.

### Task 5: Typed Omnisearch Backend And Frontend Adapter

**Files:**
- Modify: `src/argus/domain/supabase_gateway.py`
- Modify: `src/argus/api/routers/search.py`
- Modify: `src/argus/api/search_utils.py`
- Modify: `web/lib/argus-api.ts`
- Create: `web/lib/command-palette-items.ts`
- Modify: `web/components/sidebar/ChatCommandPalette.tsx`
- Create: `web/__tests__/command-palette-items.test.ts`
- Modify: `web/__tests__/alpha-frontend.test.ts`

- [ ] **Step 1: Extend backend search mapping**

In `src/argus/api/routers/search.py`, include memory-backed P1 loops:

```python
        for artifact in api_state.store.evidence_artifacts.values():
            if api_state.store.evidence_artifact_owners.get(artifact.id) != user.id:
                continue
            haystack = f"{artifact.title} {artifact.digest}"
            if query in haystack.lower():
                item = SearchItem(
                    type="evidence",
                    id=artifact.id,
                    title=artifact.title,
                    matched_text=artifact.digest,
                    updated_at=artifact.updated_at,
                    conversation_id=artifact.source_conversation_id,
                    lifecycle=artifact.lifecycle,
                    preview={
                        "digest": artifact.digest,
                        "artifact_type": artifact.artifact_type,
                        "source_run_id": artifact.source_run_id,
                        "symbols": artifact.payload.get("provenance", {}).get("symbols", []),
                        "benchmark_symbol": artifact.payload.get("provenance", {}).get("benchmark_symbol"),
                    },
                )
                scored_items.append((score_search_item(query=query, title=artifact.title, matched_text=artifact.digest), item))
```

Add similar loops for `ideas` and `decision_notes`. For completed runs, emit `type="backtest"` instead of adding a second `run` user-facing item, while keeping `run` accepted for compatibility.

Do not include raw `payload.result_card.context_packets`, route receipts, provider metadata, retry payloads, message transcripts, or public-share fields in `SearchItem.preview`.

- [ ] **Step 2: Add pure frontend adapter**

Create `web/lib/command-palette-items.ts`:

```ts
import type { HistoryItem, SearchItem } from "./argus-api";

export type CommandPaletteItemType =
  | "chat"
  | "strategy"
  | "collection"
  | "run"
  | "backtest"
  | "evidence"
  | "decision"
  | "idea";

export type CommandPaletteDisplayItem = {
  id: string;
  conversationId: string | null;
  type: CommandPaletteItemType;
  title: string;
  snippet: string;
  updatedAt: string;
  lifecycle?: string | null;
  preview?: Record<string, unknown> | null;
  source: "recent" | "search";
};

export function displayItemFromHistory(item: HistoryItem): CommandPaletteDisplayItem | null {
  if (item.type !== "chat") return null;
  return {
    id: item.id,
    conversationId: item.conversation_id ?? item.id,
    type: item.type,
    title: item.title,
    snippet: item.subtitle ?? "",
    updatedAt: item.created_at,
    source: "recent",
  };
}

export function displayItemFromSearch(item: SearchItem): CommandPaletteDisplayItem {
  return {
    id: item.id,
    conversationId: item.conversation_id ?? (item.type === "chat" ? item.id : null),
    type: item.type,
    title: item.title,
    snippet: item.matched_text ?? "",
    updatedAt: item.updated_at,
    lifecycle: item.lifecycle ?? null,
    preview: item.preview ?? null,
    source: "search",
  };
}

export function searchTypeLabelKey(type: CommandPaletteItemType): string {
  const keys: Record<CommandPaletteItemType, string> = {
    chat: "command_palette.types.conversation",
    strategy: "command_palette.types.strategy",
    collection: "command_palette.types.collection",
    run: "command_palette.types.backtest",
    backtest: "command_palette.types.backtest",
    evidence: "command_palette.types.evidence",
    decision: "command_palette.types.decision",
    idea: "command_palette.types.idea",
  };
  return keys[type];
}
```

- [ ] **Step 3: Add adapter tests**

Create `web/__tests__/command-palette-items.test.ts`:

```ts
import { describe, expect, test } from "bun:test";
import { displayItemFromSearch, searchTypeLabelKey } from "@/lib/command-palette-items";

describe("command palette item adapter", () => {
  test("keeps typed artifact search results instead of filtering to chat", () => {
    const item = displayItemFromSearch({
      type: "evidence",
      id: "artifact-1",
      title: "AAPL Backtest Evidence",
      matched_text: "AAPL versus SPY",
      updated_at: "2026-06-19T00:00:00Z",
      conversation_id: "conversation-1",
      lifecycle: "captured",
      preview: { digest: "AAPL versus SPY" },
    });

    expect(item.type).toBe("evidence");
    expect(item.conversationId).toBe("conversation-1");
    expect(item.preview).toEqual({ digest: "AAPL versus SPY" });
  });

  test("maps internal run to user-facing backtest label key", () => {
    expect(searchTypeLabelKey("run")).toBe("command_palette.types.backtest");
    expect(searchTypeLabelKey("backtest")).toBe("command_palette.types.backtest");
  });
});
```

- [ ] **Step 4: Update command palette**

In `web/components/sidebar/ChatCommandPalette.tsx`:

Replace local `DisplayItem` and `fromSearch` with imports:

```ts
import {
  displayItemFromHistory,
  displayItemFromSearch,
  searchTypeLabelKey,
  type CommandPaletteDisplayItem as DisplayItem,
} from "@/lib/command-palette-items";
```

Change search result setting:

```ts
setSearchResults(items);
```

Change `displayItems`:

```ts
const items = isFiltering
  ? searchResults.map(displayItemFromSearch)
  : recentItems.map(displayItemFromHistory);
```

Render a type pill next to the title:

```tsx
<span className="shrink-0 rounded-full border border-black/10 px-2 py-0.5 text-[10px] font-semibold text-black/45 dark:border-white/10 dark:text-white/45">
  {t(searchTypeLabelKey(item.type), "Conversation")}
</span>
```

Preview digest should use backend preview:

```tsx
const previewDigest =
  typeof selectedPreview?.preview?.digest === "string"
    ? selectedPreview.preview.digest
    : selectedPreview?.snippet;
```

Footer navigation stays single-action:

```tsx
{selectedPreview?.conversationId && (
  <button type="button" onClick={() => openItem(selectedPreview)} ...>
    <span>{t("command_palette.open_source_conversation", "Open source conversation")}</span>
    <ChevronRight className="h-4 w-4" />
  </button>
)}
```

- [ ] **Step 5: Run search tests**

Run:

```bash
poetry run pytest tests/test_alpha_api.py::test_search_returns_typed_p1_artifacts -q
cd web && bun test __tests__/command-palette-items.test.ts
```

Expected: PASS.

### Task 6: Result Card Decision UI

**Files:**
- Modify: `web/components/chat/StrategyResultCard.tsx`
- Modify: `web/lib/chat-result-actions.ts`
- Modify: `web/components/chat/types.ts`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Modify: `web/__tests__/chat-result-actions.test.ts`

- [ ] **Step 1: Add i18n keys**

In `web/public/locales/en/common.json` under `chat.result_card`:

```json
"decision": {
  "add": "Add decision",
  "note_placeholder": "Optional note for future you",
  "save": "Save decision",
  "cancel": "Cancel",
  "watching": "Watching",
  "promising": "Promising",
  "rejected": "Rejected",
  "revisit_later": "Revisit later",
  "saved": "Decision: {{state}}"
}
```

In `web/public/locales/es-419/common.json`:

```json
"decision": {
  "add": "Agregar decisión",
  "note_placeholder": "Nota opcional para tu yo futuro",
  "save": "Guardar decisión",
  "cancel": "Cancelar",
  "watching": "En observación",
  "promising": "Prometedora",
  "rejected": "Rechazada",
  "revisit_later": "Revisar después",
  "saved": "Decisión: {{state}}"
}
```

- [ ] **Step 2: Render decision form with typed API call**

In `StrategyResultCard.tsx`, import:

```ts
import { Check, Eye, FileText, XCircle, CalendarClock } from "lucide-react";
import { createEvidenceDecision, type DecisionState } from "@/lib/argus-api";
```

Add local state:

```ts
const [isDecisionOpen, setIsDecisionOpen] = useState(false);
const [selectedDecision, setSelectedDecision] = useState<DecisionState>("watching");
const [decisionNote, setDecisionNote] = useState("");
const [isSavingDecision, setIsSavingDecision] = useState(false);
const [savedDecision, setSavedDecision] = useState<DecisionState | null>(null);
```

Get artifact id:

```ts
const evidenceArtifactId =
  typeof result.evidenceArtifactId === "string"
    ? result.evidenceArtifactId
    : typeof result.metadata?.evidence_artifact_id === "string"
      ? result.metadata.evidence_artifact_id
      : null;
```

Add neutral semantic chips:

```tsx
const decisionOptions: Array<{ value: DecisionState; icon: JSX.Element; className: string }> = [
  { value: "watching", icon: <Eye className="h-3.5 w-3.5" />, className: "data-[selected=true]:border-[#6f90b8] data-[selected=true]:bg-[#6f90b8]/10 data-[selected=true]:text-[#4f7199] hover:border-[#6f90b8]/55 focus-visible:ring-[#6f90b8]/25" },
  { value: "promising", icon: <Check className="h-3.5 w-3.5" />, className: "data-[selected=true]:border-[#6ea58d] data-[selected=true]:bg-[#6ea58d]/10 data-[selected=true]:text-[#477b63] hover:border-[#6ea58d]/55 focus-visible:ring-[#6ea58d]/25" },
  { value: "rejected", icon: <XCircle className="h-3.5 w-3.5" />, className: "data-[selected=true]:border-[#b87979] data-[selected=true]:bg-[#b87979]/10 data-[selected=true]:text-[#935757] hover:border-[#b87979]/55 focus-visible:ring-[#b87979]/25" },
  { value: "revisit_later", icon: <CalendarClock className="h-3.5 w-3.5" />, className: "data-[selected=true]:border-[#b89b5f] data-[selected=true]:bg-[#b89b5f]/10 data-[selected=true]:text-[#8a713d] hover:border-[#b89b5f]/55 focus-visible:ring-[#b89b5f]/25" },
];
```

Save:

```ts
const saveDecision = async () => {
  if (!evidenceArtifactId || isSavingDecision) return;
  setIsSavingDecision(true);
  try {
    const response = await createEvidenceDecision(evidenceArtifactId, {
      decision_state: selectedDecision,
      note: decisionNote,
    });
    setSavedDecision(response.decision.decision_state);
    setIsDecisionOpen(false);
  } finally {
    setIsSavingDecision(false);
  }
};
```

- [ ] **Step 3: Add tests**

In `web/__tests__/chat-result-actions.test.ts`, add static guard:

```ts
test("result actions include decision only with evidence artifact identity", () => {
  const source = readFileSync(
    join(process.cwd(), "components/chat/StrategyResultCard.tsx"),
    "utf8",
  );
  expect(source).toContain("createEvidenceDecision");
  expect(source).toContain("evidenceArtifactId");
  expect(source).toContain("data-[selected=true]");
});
```

- [ ] **Step 4: Run frontend tests**

Run:

```bash
cd web && bun test __tests__/chat-result-actions.test.ts
```

Expected: PASS.

### Task 7: Documentation, OpenAPI, And Roadmap Status

**Files:**
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/api/openapi.yaml`
- Modify: `docs/specs/private-alpha-next-roadmap.md`
- Test: `tests/test_private_alpha_release_docs.py`, `tests/test_alpha_artifacts.py`

- [ ] **Step 1: Align API docs to shipped names**

Verify docs use:

```text
Run = internal engine execution.
Backtest = user-facing completed simulation artifact.
EvidenceArtifact = immutable proof package.
DecisionNote = explicit user judgment.
```

Search command:

```bash
rg -n "save_strategy|Run|Backtest|EvidenceArtifact|DecisionNote|IdeaVersion" docs/API_CONTRACT.md docs/DATA_MODEL.md docs/api/openapi.yaml docs/specs/private-alpha-next-roadmap.md
```

Expected: `save_strategy` remains documented only as compatibility, not P1 commitment.

- [ ] **Step 2: Mark P1 roadmap checkboxes**

Only after tests pass, update `docs/specs/private-alpha-next-roadmap.md`:

```markdown
- [x] Update spec/API/data-model docs for the exact P1 object contract.
- [x] Identify migrations, if any, and make them reversible and minimal.
- [x] Write failing backend tests for evidence capture, decision capture,
      hydration, reload, and search retrieval.
- [x] Write or update focused frontend tests for visible artifact states.
- [x] Define browser QA prompts before implementation, including messy language,
      reload, locale switch, and navigation during async changes.
- [x] Confirm rollback can be described as one clean commit revert per slice.
```

- [ ] **Step 3: Run docs tests**

Run:

```bash
poetry run pytest tests/test_private_alpha_release_docs.py tests/test_alpha_artifacts.py -q
```

Expected: PASS.

### Task 8: Verification Gate And Browser QA

**Files:**
- No production file edits unless verification finds defects.

- [ ] **Step 1: Backend focused suite**

Run:

```bash
poetry run pytest tests/test_p1_evidence_spine.py tests/test_alpha_api.py tests/test_alpha_api_supabase.py tests/test_chat_stream_contract.py tests/test_chat_runtime_reload_guardrails.py tests/test_supabase_gateway.py -q
```

Expected: PASS. Stop on any failure.

- [ ] **Step 2: Frontend focused suite**

Run:

```bash
cd web && bun test __tests__/chat-result-actions.test.ts __tests__/command-palette-items.test.ts __tests__/alpha-frontend.test.ts __tests__/chat-message-hydration.test.ts __tests__/chat-conversation-routing.test.ts
```

Expected: PASS. Stop on any failure.

- [ ] **Step 3: Anti-drift static scan**

Run:

```bash
rg -n "EvidenceArtifact|DecisionNote|IdeaVersion|add_decision|decision_state|watching|promising|rejected|revisit_later" src/argus/agent_runtime src/argus/api src/argus/domain web | head -200
rg -n "Do you want|Quieres|watching|promising|rejected|revisit" src/argus/agent_runtime src/argus/api src/argus/domain
```

Expected:
- New product state is outside `llm_interpreter.py`.
- User-facing decision labels appear in frontend locales or presentation helpers, not runtime core.
- No translated labels are used as branching conditions.

- [ ] **Step 4: Launch local QA server**

Use QA or dev mode depending on available credentials:

```bash
.github/dev.sh
```

In another terminal:

```bash
cd web && NEXT_PUBLIC_MOCK_AUTH=true NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8000/api/v1 bun run dev -- --host 127.0.0.1 --port 3031
```

Expected:
- Backend health is reachable.
- Frontend opens at `http://127.0.0.1:3031/chat`.

- [ ] **Step 5: Live browser QA flows**

Use Codex browser on `http://127.0.0.1:3031/chat`:

1. Messy English:
   - Prompt: `let's test holding AAPL MSFT and TSLA from 2023 to date with 100k, compare it with QQQ if possible`
   - Expected: confirmation and result preserve symbols, date, capital, and benchmark.
   - Expected after run: result card has an `Add decision` affordance only once.
2. Decision:
   - Click `Add decision`, choose `Promising`, add note `Watch relative strength.`, save.
   - Reload.
   - Expected: decision state persists and does not duplicate cards.
3. Omnisearch:
   - Search `AAPL`.
   - Expected: typed results include `Conversation`, `Backtest`, `Evidence`, `Decision`, `Idea`.
   - Expected: right preview shows backend digest, not raw JSON/code.
   - Expected: single footer/source navigation action.
4. Spanish:
   - Switch language to Spanish.
   - Search same symbol and open result preview.
   - Expected: static UI labels translate; typed state remains stable.
5. Async navigation:
   - Start another backtest, navigate to another chat during execution, return.
   - Expected: no duplicate ready/result cards and no invented decision state.

- [ ] **Step 6: Internal code review**

Use `superpowers:requesting-code-review` after implementation and before promotion. Required review prompt:

```text
Review the P1 evidence decision spine on codex/private-alpha-next-reintegration.
Focus on language-agnostic runtime boundaries, modularity, P0 continuity regressions,
evidence/decision object correctness, RLS ownership, search/Omnisearch UI truth,
and whether any user-facing state is inferred from prose or translated labels.
```

- [ ] **Step 7: Commit and promotion readiness**

Commit only after all gates pass:

```bash
git status --short
git add docs/API_CONTRACT.md docs/DATA_MODEL.md docs/api/openapi.yaml docs/specs/private-alpha-next-roadmap.md src/argus/api src/argus/domain supabase/migrations tests web
git commit -m "feat(p1): add evidence decision spine"
```

Expected:
- One coherent P1 commit, or a short series of coherent commits:
  - `test(p1): define evidence decision contract`
  - `feat(p1): add evidence decision spine`
  - `feat(search): surface typed evidence recall`
  - `docs(p1): record shipped evidence decision contract`
- Promotion to `codex/private-alpha-next` happens only after founder approval.

## Self-Review

- Spec coverage: P1 object contract, evidence auto-capture, decision capture, typed Omnisearch, docs, tests, browser QA, and promotion discipline are represented.
- Deferred by design: standalone ledger dashboard, RAG/vector memory, broker/export, public excerpts, voice/STT, PostHog, full cost ledger implementation.
- Type consistency: user-facing `Backtest` maps to backend `backtest_runs`/internal Run; `EvidenceArtifact` and `DecisionNote` are typed Pydantic/TypeScript objects; lifecycle and decision states are stable literals.
- Anti-drift scan: no new localized semantic routing is planned; new localized text is restricted to frontend locales or existing presentation label-key paths.
