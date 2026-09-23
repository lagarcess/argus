# Local Argus conversation

This runtime is local and separate from the production application bootstrap.
Its typed financial capabilities reuse the existing ledger, planning, investing,
service, memory and calculation owners. It makes no financial write without a
user confirmation. Free text requires an explicitly configured semantic model;
prepared actions work without one.

All routes below are relative to `/api/platform/chat` and require the current
local household session. Viewers may read and export; all conversation and turn
mutations require current editor or owner authority, including turn replay,
checkpointing and settlement.

| Method and route | Contract |
| --- | --- |
| GET `/capabilities` | Command and calculation declarations, read capabilities, typed examples and model availability. The catalog derives from the registered owners. |
| GET `/context` | Bounded owned account and record choices; optional `account_id`. |
| POST `/conversations` | Create a conversation with an optional title. |
| GET `/conversations` | Filter by state; bounded `limit` and `offset`. |
| GET `/conversations/{id}` | Conversation plus a bounded page of immutable messages. |
| PATCH `/conversations/{id}` | Rename, pin, archive, trash or restore. |
| GET `/conversations/{id}/export` | Complete bounded transcript attachment, or a clear size error. Internal plans, turn requests and provider metadata are excluded. |
| POST `/turn` | Exactly one of free text or typed action, with a unique `turn_id` and optional conversation/context. |
| PATCH `/proposals/{id}` | `expected_revision`, changed input fields and revision `request_id`. |
| POST `/proposals/{id}/confirm` | Only `expected_revision`; the proposal owns identity, input and replay. |
| POST `/proposals/{id}/cancel` | Only `expected_revision`. |

The turn stream contains canonical data-only `stage_start`, `stage_outcome`,
`final` and `[DONE]` frames. The final result is durable before delivery. A failed
or interrupted response can be retried with its original turn ID and unchanged
payload. A changed payload cannot reuse that ID. An active execution lease
prevents a second writer. A checkpointed plan resumes without another model
read.

Plans select reads, record queries, calculations, proposals, proposal revisions,
clarification or unsupported behavior. Confirmation is absent from the model's
plan schema. Financial answers render canonical evidence-bearing cards. The
model can ask for missing information but cannot invent financial output.

A confirmed write, consumed proposal, receipt and transcript message share one
transaction. The domain writer is the same writer used by the manual UI.
Identity, household generation, role, expiry and dependencies are checked inside
that transaction. Changed or deleted data cannot silently revive an old proposal.
Shared household members can read a conversation; proposal mutations remain
restricted to its creator and current write authority.

Record and calculation evidence includes the owned record or source and its
date. Exact account and transaction references resolve before their currency is
chosen, in the same snapshot as the returned facts. `currency` means an explicit
request denomination; `default_currency` is only a display hint. The hint cannot
overrule a stated currency or an owned record. An anchored artifact keeps
its denomination; a new artifact can use a newly stated currency. No path
silently converts money. See [guest and currency](guest-and-currency.md).

Proposal currency sources distinguish `account`, `record`, `explicit` and
`ui_default`. A default is labeled as the app currency preference, never as
something the person stated. Calculation cards use the copied core's
`assumption` source for the same default. Non-currency edits retain that source;
an explicit currency edit replaces it. Reload reads persisted provenance.

The copied Argus calculation catalog and result-card semantics are described in
[core reuse](../experience/CORE_REUSE.md). The planner is one LangGraph owner with
explicit OpenRouter configuration, bounded admission and no automatic retries.
The installed SDK transport is tested with mocked HTTP; live interpretation
quality and latency remain unverified. See [Jev assessment](../experience/JEV.md).

Older assistant receipts remain readable through their existing API and the
full-canvas legacy bridge. No silent migration rewrites those records.

## Bounds

Context carries at most 30 ordinary record choices, eight explicit mentions,
12 recent messages and enabled, explicitly confirmed memories. Explicit record
references outside the choice window are still validated against their owner.
Context/message limits are 256 KiB; transcript responses are capped at 2 MiB.
Exports fail rather than truncate beyond 10,000 rows per table or 8 MiB overall.
Calculation continuation resolves anchors in the latest 100 messages; older
unavailable anchors are not reconstructed from prose.

Browser drafts use an opaque route ID and session storage scoped to user,
household and canonical data generation. Editing a submitted draft invalidates
its old turn ID. Route changes abort pending delivery and prevent stale results
from changing the current page. Server-accepted work remains recoverable from
its conversation.

The composer owns the serialized draft and its edit identity. Persistence and
delivery use that same snapshot, including line breaks and record mentions.
Ordinary completion and inline retry acknowledge only the submitted edit;
newer text survives. Typed-action completion does not acknowledge a text draft.
