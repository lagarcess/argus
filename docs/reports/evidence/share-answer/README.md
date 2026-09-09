# Share the answer evidence

This is local acceptance evidence for the existing receipt pipeline. GitHub CI,
the exact-head Codex review and terminal audit are recorded on the lane PR; this
file alone does not claim release readiness. Checked-in sharing flags remain off.

## Environment and provenance

The production Next build used the real local Argus API and an isolated Supabase
stack (web 3319, API 8319, Supabase 55431/55432). Owner creation, preview, publish,
Settings, revoke and public reads were not API stubs. No hosted Auth/database,
production configuration or deployment was changed. Private credentials, original
messages, source ids and browser storage remain in ignored `temp/share-answer-qa`.

The two published research answers came from the configured real research rail,
in English and Spanish, at backend source `bd420a63`. They were reused for all
browser work without another retrieval. The first, broader English request timed
out at the research provider and was correctly ineligible; it is not counted as
successful research proof. [Provenance](research-provenance.json) records all three
attempts. [Adversarial checks](real-turn-adversarial.json) attack copies of both
successful turns through the actual selection projector: 18 named refusals,
unchanged answer/source content, no metadata expansion, no writes or new calls.

The selection examples are explicitly authored fixtures. The DCA example uses
one injected synthetic price series through production signals, metrics,
benchmark, chart, card and finalization code; it is not live market evidence.
Identifiers displayed in refusal examples are random test strings, not owner
identifiers. The audit is the existing identifier/credential audit, not a claim
of general personal-information detection.

## Browser evidence

Every public matrix covers 390 and 1280 CSS pixels with `en` and `es-419` reader
chrome. The original author language remains unchanged. Public reads returned200,
with no cookies, no horizontal overflow, and `noindex, nofollow, nocache`.

| Proof | Records and representative images |
| --- | --- |
| Final chat has one header glyph, no bubble/card share pills; sources remain | [Records](header-final-result.json), [phone](research-es-419-header-390.png), [desktop](research-es-419-header-1280.png) |
| English research, signed out | [Matrix](research-en-focused-public.json), [phone](research-en-focused-390-en.png), [Spanish reader](research-en-focused-390-es-419.png) |
| Spanish research, signed out | [Matrix](research-es-419-public.json), [phone](research-es-419-390-es-419.png), [desktop](research-es-419-1280-es-419.png) |
| Four selected turns, including DCA contribution, zero principal and modeled costs | [Matrix](mixed-public.json), [English desktop](mixed-four-1280-en.png), [Spanish phone](mixed-four-390-es-419.png) |
| The original result card reads the same DCA facts and has no share control | [Records](dca-card.json), [English phone](dca-card-390-en.png), [Spanish desktop](dca-card-1280-es-419.png) |
| Eligible-only selection and readable refusal reasons | [English](selection-en-result.json), [Spanish](selection-es-419-result.json), [English phone](selection-390-en-reasons.png), [Spanish phone](selection-390-es-419-reasons.png) |
| Refusal identifies question, answer and owner note | [English fields](selection-1280-en-fields.png), [Spanish fields](selection-1280-es-419-fields.png), [English note](selection-390-en-note.png), [Spanish note](selection-390-es-419-note.png) |
| Five eligible turns: no arbitrary Select all, manual cap four | [Records](cap-five-result.json), [phone](cap-five-390-en.png), [desktop](cap-five-1280-en.png) |
| Same Settings list and revoke | [Records](settings-revoke.json), [before](settings-revoke-before.png), [after](settings-revoke-after.png) |
| Revoked research link becomes the same tombstone | [Matrix](tombstone-public.json), [English phone](tombstone-390-en.png), [Spanish phone](tombstone-390-es-419.png) |
| Existing SSR preview card supports research/mixed | [Records](preview-cards.json), [Spanish research card](research-es-419-preview-card-es-419.png) |
| Continue with Argus lands at bare guest entry | [Records](public-entry-result.json), [loaded entry](continue-guest-entry.png) |

The header selection opens without publishing. Preview is one read request;
Make the link is one creation request. One checked answer creates a singleton
wrapper. Reusing a live selection makes a fresh creation/validation request and
returns the same record. Re-sharing after manual revoke creates a new record;
the revoked link remains dead. [Creation/lifecycle records](creation-lifecycle.json)
retain no private snapshot or source ids.

The DCA browser case exposed a real direct-run configuration shape missing its
contribution and principal in shared readouts. The fix derives the existing slots
from the engine's canonical capital plan for both card and receipt readers. The
old local mixed link was revoked through Settings and the same four turns were
selected again through the header. Its frozen payload was never rewritten.
Refreshed proof shows $0 principal, $200 monthly, 10 bps fee and 5 bps slippage in
both languages. Only that affected acceptance was invalidated; the research,
selection/refusal and lifecycle evidence was retained.

The CTA has literal href `/`; normal guest bootstrap settles at `/chat` with no
query, fragment, assistant turns or composer text. One beacon request was observed
for the public render and one for the CTA. The browser bridge omits Beacon Blob
bodies, so typed `stage`/`kind` payloads are established by the focused tests.
Unknown/revoked pages omit kind-attributed events rather than inventing a kind.

[History/focus trace](header-lifecycle.json) verifies two open/Escape cycles at
both widths, one push per open, no premature Back and focus restored to the
header. [Playwright regression](focus-playwright.txt) passes both widths using
the existing mocked shell fixture; it is separate from the real-API proof above.

## Version 1: exact compatibility

[Comparison](v1-comparison.json) is exact in all four combinations: main HTML,
text, bounding box and pixels. [Before](v1-before.json) and [after](v1-after.json)
retain the unmodified main DOM. The baseline came from web source `66730237`
(integration `743dfda3` plus docs only), serving the previously committed v1
receipt JSON verbatim. The final public read comes from an actual v1 row in the
local database. It remains an unwrapped v1 payload.

The comparison images capture only the receipt body. Screenshot-only CSS hides
the fixed action bar (whose CTA intentionally changes) and the development
indicator. It does not alter recorded HTML/text. Public-page matrices separately
capture the whole page and action bar. No source body was rewritten to make the
comparison pass.

## Deterministic verification and revalidation

- [482 backend checks](backend-focused.txt), including 57 new DCA reader cases;
  [23 OpenAPI checks](openapi-checks.txt).
- [60 real PostgreSQL checks](postgres-sharing.txt), zero skips: shared selections,
  insertion/deletion races, role grants, immutability, browser denial and handoff.
- 1,653 Bun tests; two exact v1 snapshots; frontend lint has zero errors and eight
  existing warnings. Production Next build passes. Standalone full-project tsc
  retains pre-existing test-declaration failures; the production build and runtime
  types pass without suppressing those failures.
- 243 mocked runtime eval checks were run; sharing changes no interpreter prompt
  or research provider behavior. No broad paid rerun was performed.
- [Modularity](modularity.txt) passes against the already-reconciled tree.

[Runtime trees](runtime-source.json) bind the built code independently of later
documentation/evidence commits. The final PR audit explicitly revalidates these
unchanged trees at the exact PR head, and is written only after the final review
returns. Original and freshly fetched integration both equal `743dfda3`; no merge
commit or overlapping integration delta was needed.

The focused final code review cleared `9531c164..dfb86ef8`, including 57 passing
reader tests, with no actionable finding. Version 1 was re-read and compared again
after that backend fix: all four HTML, text, box and RGB pixel comparisons remain
exact. This local review does not replace the exact-head GitHub Codex round.

Drivers live in [drivers](drivers). Inputs containing credentials or source ids
are supplied from ignored local storage. The v1 transport driver is baseline-only;
it is never used for auth, creation, source eligibility or revocation acceptance.
