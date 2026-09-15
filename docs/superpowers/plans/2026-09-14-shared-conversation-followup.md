# Shared conversation follow-up implementation plan

**Goal:** A shared frozen thread leads into the receiver's own normal chat on
first submit, preserving owner privacy and receiver allowances.

**Architecture:** Public presentation derives exclusively from the receipt.
A separate authenticated write transaction imports ordinary messages with shared
provenance. The existing guest admission, choice, signup handoff and chat send
paths own the receiver's next turn.

**Spec:** ../specs/2026-09-14-conversation-sharing-604.md

## Global constraints

No paid calls without founder go; no prompt/fingerprint changes; no render.yaml
or release contracts; no stash, founder-owned PR merge or deploy. No hidden source data or live
cards. One Codex review, stop on second finding on the same mechanism.

## Work and ownership

- [x] Backend: `public_excerpt_forks` service and isolated authenticated router;
  typed request/response, transactional idempotency, live-snapshot validation,
  guest replacement consent, 64KiB text and 512KiB total payload limits;
  naming exclusion and count-only stages. Tests cover memory and real Postgres
  races, revoked/deleted input, retained copies, isolation and guest handoff.
- [x] Presentation: ReceiptBody and stateless thread/card primitives plus locale
  receipt copy. One renderer for public/preview/carried cards; all answer kinds,
  theme parity, dates, owner note at top, notice, footer composer, shared widths.
- [x] Bridge: session-only pending submission, request id retry identity, normal
  guest admission and existing choice/conversion, fork API, canonical hydration,
  one normal send; imported message mapping to frozen read-only rendering.
- [x] Captain: fixture timestamp red/green regression; add calculation fixture;
  update API/data/spec contracts and regenerate OpenAPI. Provider-free motion-on
  screenshot matrix for public and preview, read frames, no private IDs or writes
  on view. Focused tests, mocked eval, fingerprint and merged-tree modularity.
- [ ] Reconcile latest integration one-way, record semantic overlap and exact
  evidence head. Publish PR, one Codex review, resolve bounded findings, check CI
  and unresolved threads. Offer capped $1 live acceptance and wait for go.

Each worker supplies red/green evidence and a bounded final report; the captain
owns integration and review. Completed agents have no standing follow-up.
