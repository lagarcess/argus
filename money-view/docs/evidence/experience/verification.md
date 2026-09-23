# Argus finance experience verification

Source checkpoint: `06980d1961f166500ffd6d362a084a27802e27bb`.
Original and last verified private integration base:
`5430d98d61d815e6c4a2bed60213b411a2bb875e`.
Only destination: `codex/money-placement-pilot`.

## Scope and outcome

Argus's adapted composer, conversation, guest landing, Omnisearch, recents and
settings surround the existing local finance platform. Chat and manual controls
reach the same canonical domain writers. The command registry covers 28 writes;
11 hash-pinned Argus calculations retain their original algorithms. Sources,
dates, explicit confirmation, currency provenance and durable receipts remain
reader-visible. Statement intake maps and previews bounded CSV/TSV data before
confirmation. The local guest can use seeded data or begin with no records.

The final delivery fixes address shared owners: proposal edit state controls
confirmation; route scope controls history loading; composer snapshot/edit
identity controls send, retry and persistence; currency resolution preserves
inferred versus explicit sources through edits and reload.

## Deterministic verification

Fresh local checks on the committed application sources:

| Check | Result |
| --- | --- |
| Python application regression | 700 passed in 99.03 seconds; one third-party Starlette/AnyIO deprecation warning |
| Generated Argus core | 28 generated files verified |
| Ruff, server/tests/scripts | Passed |
| Frontend unit behavior | 24 passed |
| TypeScript and Vite build | Passed; Vite build 836 ms |
| Delivery browser regressions | Five passed; whitespace, multiline, mention, ordinary send/reload, newer edits, typed actions, staged handoff |

The 60-case browser run completed with 59 passes and one test timing failure:
import completion's deferred history traversal raced an immediate test reload.
The test now waits for the canonical overlay marker to clear. The affected
EN/ES import flows and the complete responsive experience matrix then passed,
14/14. See [summary](final/summary.json), [full run](final/browser-full.txt) and
[follow-up](final/browser-followup.txt). No application source changed for this
correction. GitHub CI will rerun all 60 cases together.

Browser acceptance under [final](final/) uses
loopback-only Vite/API processes and temporary databases with all provider keys
blank. The five delivery tests explicitly intercept model capability and SSE
responses to exercise the browser lifecycle. They do not prove language-model
quality. Other journeys exercise the real local API. Provider and test fixture
boundaries are visible in the test files and logs.

## Scoped review closure

The historical findings and later clean verdicts are retained in full. Read the
latest section of each record; early findings are retained as history.

- [Core reuse](reviews/core.md), [identity](reviews/identity.md),
  [imports](reviews/import.md), [commands](reviews/commands.md),
  [chat runtime](reviews/chat.md), [search](reviews/search.md) and
  [settings/history](reviews/settings-history.md) reached clean scoped reviews.
- [UI history](reviews/ui-history.md) records the original three lifecycle
  findings. Proposal and pagination fixes closed there; the
  [delivery closure](reviews/delivery.md) closes the last P2 and the staged
  cleanup P3. The [currency delta](reviews/currency-provenance.md) is also clean.
- Two trailing blank lines were removed from test files after review. They do
  not change test or product behavior. Final source manifests include them.
- [Prior PR audit](../../PR_REVIEW_AUDIT.md) confirms clean latest-delta
  acknowledgment and zero unresolved threads for the previous private merges.

GitHub CI/review and the private merge remain required delivery steps. Their
terminal state will be recorded in the PR after the final reviewer response,
including current head, base, unresolved threads and merged-tree equivalence.

## Evidence and interpretation limits

The original browser run is retained under [browser](browser/): 50 passed and
one obsolete export-filename expectation failed. The expectation was corrected;
that earlier run is not represented as all-green acceptance. Settled screenshots
wait for fonts, two animation frames and lazy-loaded recent history. The
[visual inspection](visual-inspection.md) is separate from automated overflow
and composer geometry. Final sources, tests, dependencies and public assets are
fingerprinted in 242 entries. The full run had no drift; the follow-up changed
only the two named test files. The final evidence commit can be revalidated by
matching these hashes, preserving browser proof without rerunning unchanged
application journeys for documentation-only changes.

All ordinary vendors, identity profiles, finances, deposit publications and
service workflows remain fixtures. Local claim uses a local password; there is
no hosted identity/email service. Live bank/inflation source readiness and reuse
permission, live interpretation accuracy/cost/latency and Jev benefit are
unverified. No provider/model call was made in this completion pass.

The prior five-million-row, two-worker capacity runs and their source hashes
remain historical evidence for the previous finance platform. They establish
neither full experience capacity nor a production SLA. Target hosting hardware,
full-retention workload and sustained heavy-household traffic still require
qualification; 10,000 monthly users is not 10,000 simultaneous requests.

No deployment, Supabase migration, production environment access, real-money
execution or push/merge into `main` or `codex/private-alpha-next` occurred.
