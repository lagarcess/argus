# Shared conversations and receiver follow-ups

Founder-locked 2026-09-14. Supersedes this spec's earlier prohibition on public
fork and continuation state. The selected frozen receipt remains the privacy
boundary; continuation belongs solely to the receiver.

## 1. Outcome

A receiver sees Argus answering a real question in a read-only chat thread, then
asks a follow-up that starts their own chat. Viewing never creates a workspace,
conversation, run or charge. PRODUCT.md's conversation-first direction and the
Sharing lane of the grounded-finance roadmap govern this work.

## 2. Locked decisions

1. Anyone with the link can read it, with no access list or sign-in wall.
2. Render each selected question as a user bubble and final answer as an Argus
   reply. Backtest, calculation, sourced research and plain answers use chat's
   visuals with frozen public fields only. The owner note is at the top. Show
   the snapshot date and explain that follow-ups start the receiver's own chat.
   Owner preview uses the identical layout; unfurl images may retain figures.
3. A bottom follow-up composer initiates a receiver-owned fork only on submit.
   Signed-in receivers get an account chat; signed-out receivers enter the
   ordinary guest flow. Later follow-ups use the resulting conversation.
4. Carry each selected question, shortened final answer and bounded public
   facts as ordinary history. Never carry the owner note. Trim deterministically,
   without a model call. History text has a total 64 KiB UTF-8 bound, divided fairly across
   selected questions and answers. Carried text plus card metadata is bounded
   at 512 KiB; oversized public facts are refused before any write. No model
   summary is generated.
5. Carried backtests and calculations are frozen read-only cards, with no live
   run, artifact or execution state. Changes go through the receiver's normal
   interpretation, confirmation and allowances.
6. Reuse guest entry, its existing new-conversation choice, fixed workspace
   lifetime, caps, budgets and signup handoff. Never silently overwrite a guest
   conversation; Start over requires that existing choice.
7. Label carried history as from a shared conversation with its date. Imported
   turns cost nothing and are excluded from interest greetings, memory and
   conversation naming. The receiver's own follow-ups behave normally.
8. A guest signup retains the fork through the existing guest handoff.
9. Date snapshot figures. Current-figure questions take the normal fresh-answer
   path rather than treating frozen figures as current data.
10. Extend count-only funnel stages with followed_up and signed_up alongside
    try_argus. Add no viewer identifier.

## 3. Retained boundaries and no-touch areas

Keep frozen snapshots, owner selection, exact preview, receipt records, revoke,
tombstones, source deletion cascade, noindex and rate limits. A revoked, deleted
or tombstoned link cannot create a fork; existing receiver copies survive.
No new model-facing instruction text and no prompt fingerprint change. No private
id-dependent chat components on the public page. Public fields may derive only
from selected turns. No owner activity becomes receiver activity.

Do not touch render.yaml or release contracts. Sharing flags remain false there
and may be enabled only in isolated local fixtures. No paid calls during build.
No git stash, hosted migration, PR merge or deployment.

## 4. Contract and implementation gates

Update API_CONTRACT.md and DATA_MODEL.md and regenerate OpenAPI for all route or
field additions. Prefer existing message metadata and receipt records. If atomic
fork creation requires a migration, it must be additive and its classification
reported. Follow BREAKPOINTS.md and DESIGN.md section 8 using shared responsive
primitives. No em dashes in user-facing English or Spanish copy.

Use one public presentation owner for page, exact preview and read-only carried
cards. Use receiver authentication for writes and revalidate snapshot liveness at
fork admission. Protect retries/concurrency with durable idempotency. Do not seed
runtime execution state or copy sender identifiers into the receiver's history.

## 5. Execution contract

One worker PR targeting codex/private-alpha-next. Original fetched integration
base: `350e3dca8f573f5dfd61f1f753d8ed16a2724c9e`.

Test first: view creates nothing; first submit creates exactly one fork; retries
and later follow-ups reuse it; trimmed context excludes note and stays bounded;
revoked/deleted/tombstoned cannot fork; guest/account ownership and existing guest
choice; no imported usage or personalization/naming/memory; read-only cards and
receiver-owned changed confirmation; guest signup retention; frozen fingerprint.
Use scripts/qa/sharing_604_fixture.py without providers, fixing its seeded job's
missing updated_at and finished_at. Capture public page and preview with motion
on in English dark at 390/720/1024/1280 and Spanish light at 390. Include every
answer kind and an explicit recurring-contribution backtest. Commit evidence.

Merge latest integration into the worker, preserving both sides' intent in any
conflict. Report semantic overlap, retained/invalidated evidence and merged-tree
modularity check. Founder update 2026-09-15: PR #643 stays ready throughout
review. Validate every finding against these locked decisions; fix confirmed
findings at their owner with pattern-wide coverage and tests, or decline with
the reason. Reply on and resolve every thread, push, wait for green CI, then
request the next Codex review. Repeat until the current head is clean with zero
unresolved threads. Never return this PR to draft.
When other gates are green, propose a live check capped at $1.00: signed-out
receiver opens link, asks one plain follow-up and one fresh-figure question;
report actual per-follow-up cost. Wait for founder go before spending. Keep
the already-ready PR ready throughout; after approved acceptance, stop. Founder merges.

## 6. Stop conditions

- New model instructions or changed prompt fingerprint are needed.
- Rendering requires anything beyond selected frozen public turn fields.
- A finding requires changing a locked decision, a migration, render.yaml or a
  release contract. Repeated findings alone no longer stop this review loop.
- Live calls lack explicit approval under the proposed maximum $1.00 cap.

## Sources

Founder instructions 2026-09-14; issue #604 and PR #632 history; PRODUCT.md;
argus-grounded-finance-roadmap.md Sharing lane; private-alpha-next-decision-memo.md
sections 5.8 and 10.7. The new founder decisions override older no-fork clauses.
