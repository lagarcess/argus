# Research cache identity and eligibility (#689)

Prevent cross-request answer reuse when meaning differs, and keep private
material out of shared research storage.

## 1. Why

Issue #689 identifies provider inputs omitted from shared cache identity.
PRODUCT.md requires honest assumptions and continuity; MVEE section 5 requires
privacy for personal financial information. Hashing private text is not a
public-data boundary.

## 2. Locked decisions

1. Trace provider inputs, inline lookup/write, job completion, and discovery.
2. Eligibility comes before identity. Requests without trusted public-only
   inputs must bypass shared storage, even if their text matches exactly.
3. Eligible public requests share only when their effective provider inputs
   agree. Normalize only distinctions the provider request already erases.
4. Old entries and persisted job keys must not bypass current eligibility.
5. Preserve prompts, model schemas, routing, calculations, provider behavior,
   admission, publication, and the research-to-simulation boundary.

## 3. Reserved / parked scope

- No privacy classifier, interpreter change, personalized shared cache, or
  public/private schema redesign. Recommend a separate contract if needed.
- No #710 logging callers or global logging machinery.
- No live providers, paid evaluations, customer data, hosted changes, merge,
  deployment, or main promotion.

## 4. Contract gates

- Update docs/API_CONTRACT.md cache behavior if eligibility narrows.
- No HTTP schema, migration, model-facing text, or UI change is expected.
- Existing cache TTL and bounded retention remain applicable to eligible data.

## 5. Execution contract

- One worker PR targeting codex/private-alpha-next; stop at a draft PR.
- Starting integration: 61ef59d12f0f38ab3df507712e02f17991bedced.
- Reproduce collisions using synthetic requests and mocked provider packets.
- Cover changed dimensions, safe normalization, private exclusion, inline and
  job completion, old identity rejection, and useful eligible cache reuse.
- Run research tests, mocked eval harness, repository lint/ownership/modularity
  gates and provider-free suite. Record baseline failures separately.
- Scoped independent review and GitHub Codex review; dispose findings and check
  unresolved threads. Reconcile integration one way and audit semantic overlap.
- No UI or live-provider acceptance is claimed by deterministic evidence.

## 6. Stop conditions

If safe reuse needs new model instructions, private-data classification, or
provider changes, complete the safe bounded bypass and recommend that separate
contract in the draft. Report unavailable checks without waiving them. Never
absorb concurrent #710 work.

## Sources

- [Issue #689](https://github.com/lagarcess/argus/issues/689)
- ../../PRODUCT.md
- ../../DOCUMENTATION_AUTHORITY.md
- ../../specs/argus-minimum-viable-ecosystem-experience.md
- ../../API_CONTRACT.md
- ../../../AGENTS.md

Inference: unrestricted request text cannot be certified public merely by its
research tool name, presence of citations, or omission of account identifiers.
