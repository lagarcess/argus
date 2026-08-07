# Legacy Collections and Strategies Removal

Remove the retired Collections and Strategies product surfaces while keeping
historical database records safe to deserialize and reference.

Founder-locked 2026-08-06, after the Idea / Evidence / Decision recall loop
replaced the old saved-strategy product center and the active roadmap explicitly
scheduled the strip-out as standing chore work.

## 1. Why

Argus is chat-first, and the current private-alpha product surface is Chat,
Recents, Omnisearch / Idea Ledger, and Settings. The dedicated Strategies and
Collections views are dead ends that no longer help a normal person test or
revisit an idea faster. Keeping their code and environment switches creates a
false product contract and expands the release surface without user value.

Authority:

- `docs/PRODUCT.md` says conversation is the product and Omnisearch / Idea
  Ledger owns current saved-idea recall.
- `docs/specs/argus-active-roadmap.md` explicitly directs the repository to
  strip the legacy Collections and Strategies code while leaving
  `ARGUS_ASSET_PROVIDER_MODE` intact.
- `docs/specs/private-alpha-next-decision-memo.md` records that the old
  Strategies destination must not be carried into the Idea / Evidence /
  Decision object model and allowed destruction only after an explicit removal
  decision. This spec is that explicit decision.

## 2. Locked decisions

1. Delete `CollectionsView`, `CollectionPicker`, and `StrategiesView`, remove
   their navigation and mount paths, and remove tests that exercise those
   retired surfaces.
2. Remove the browser API clients and FastAPI CRUD routers used only by those
   surfaces. New code cannot create, rename, pin, delete, attach, or list
   Collections or saved Strategies through dedicated endpoints.
3. New result cards expose only current result actions. They do not emit or
   render the legacy `save_strategy` action. A stale client or persisted action
   may still reach the chat compatibility path, but that path can only explain
   that the result remains available in conversation/history; it cannot create
   a Strategy.
4. Keep the `Strategy` and `Collection` read models, existing tables,
   migrations, ownership data, historical `strategy_id` references, and the
   readers required to deserialize old rows. Do not migrate, delete, rewrite,
   or reinterpret historical records.
5. Keep direct backtest loading of an owned historical `strategy_id`. It is a
   read-safe compatibility path over an existing record, not a dedicated
   Strategies surface or a new write path.
6. Remove `ARGUS_STRATEGIES_ENABLED`, `NEXT_PUBLIC_STRATEGIES_ENABLED`, and
   `NEXT_PUBLIC_COLLECTIONS_ENABLED` from the complete release contract:
   `.env.example`, `web/.env.local.example`, `render.yaml`,
   `.github/private-alpha-release-profile.json`, `.github/argus-env.sh`, local
   smoke / QA environment writers, and active setup documentation.
7. Leave `ARGUS_ASSET_PROVIDER_MODE` and its fallback relationship with
   `ARGUS_MARKET_DATA_PROVIDER_MODE` unchanged.
8. The `ChatInterface.tsx` diff is limited to code whose only purpose is the
   retired Strategies view or its legacy Save action. No opportunistic cleanup,
   formatting, or unrelated refactor is allowed in that file.
9. Browser acceptance must show ordinary chat, the chat-only sidebar, and
   Settings unchanged in English and Spanish-compatible runtime state. Durable
   screenshots are committed under `docs/reports/evidence/legacy-surface-removal/`.

## 3. Reserved / parked scope

- Database table or migration removal is parked because destructive schema
  cleanup would violate historical read safety.
- Removing `strategy_id` from `BacktestRun`, backtest responses, job payloads,
  or the owned historical direct-run read is parked because those identities
  belong to immutable historical evidence.
- Generic uses of the word `strategy` in interpretation, confirmation,
  execution, evidence, dossiers, and backtesting are protected current product
  behavior and are not part of this removal.
- Postgres History and Search compatibility readers may retain legacy
  Strategy / Collection branches when they are needed to tolerate old rows;
  this lane does not redesign their pagination or ranking.
- No deployment, merge, database migration, or hosted environment mutation is
  authorized.

## 4. Contract gates

- `docs/PRODUCT.md` -- replace flagged-surface language with retired-surface and
  compatibility-record truth.
- `docs/ARCHITECTURE.md` -- remove live surface/router ownership and document
  read-only legacy persistence.
- `docs/API_CONTRACT.md` -- remove dedicated CRUD endpoint contracts, stop new
  `save_strategy` production, and document stale-action compatibility.
- `docs/DATA_MODEL.md` -- retain tables and relationships as legacy read-safe
  records with no current creation surface.
- `.agent/designs/argus/DESIGN.md` -- remove future flagged UI guidance and
  state that old actions are never rendered.
- `docs/CONVERSATIONAL_RUNTIME.md` and
  `docs/QA_CONVERSATIONAL_TRANSCRIPTS.md` -- remove active flag instructions.
- `docs/api/openapi.yaml` -- regenerate from canonical `app.openapi()` after the
  dedicated routers and write schemas are removed.
- `.github/private-alpha-release-profile.json`, `render.yaml`, and
  `.github/argus-env.sh` -- move together as one hosted release contract.

## 5. Execution contract

- **PR shape:** one worker branch with a spec commit followed by one atomic
  implementation commit. The user asked for a pushed branch only; no PR is
  opened unless separately requested.
- **Proof required before ready:** focused red/green removal tests, full Bun
  frontend suite, full pytest backend suite on the pinned Python runtime, full
  Ruff check, a production frontend build, environment-contract checks,
  regenerated OpenAPI compatibility, and real-browser screenshots of ordinary
  chat, sidebar, and Settings. Any failure is compared with a clean worktree at
  base `9664e221fa50187d6b078ccdfcffd90cbc76d852` before classification.
- **Where it stops:** commit locally, push the worker branch, and report exact
  evidence. The founder retains merge and deployment authority.

## 6. Stop conditions

- If historical rows require a destructive migration, column removal, or data
  rewrite, stop and report.
- If removing a dedicated router breaks an active Chat, Recents, Omnisearch,
  Settings, backtest, evidence, decision, guest handoff, or canary path, stop
  and narrow the removal rather than deleting that current path.
- If `ChatInterface.tsx` requires unrelated restructuring or overlaps an open
  PR beyond the Strategies view / Save-action lines, stop and report the
  overlap.
- If browser proof requires paid provider or hosted workflow execution, use the
  deterministic local stack instead; do not spend or deploy without separate
  authorization.
- If the exact integration branch advances before the ready report, reconcile
  one-way, audit semantic overlap, and rerun only invalidated evidence.

## Sources

### Argus authority

- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `.agent/designs/argus/DESIGN.md`
- `docs/specs/argus-active-roadmap.md`
- `docs/specs/private-alpha-next-decision-memo.md`
- Commit `88ae8c77aa9c35c46e986dff8157d50c98c07d3e`

### Inference

- Keeping base models, old foreign-key identities, and compatibility readers
  while deleting all dedicated write surfaces is the narrowest equivalent of
  the onboarding strip-out's inert-state/read-filter boundary.
