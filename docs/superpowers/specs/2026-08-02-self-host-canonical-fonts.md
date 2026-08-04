# Self-host canonical Argus fonts

Status: **COMPLETED** — PR #348 merged into `codex/private-alpha-next` as
`38874baecde59ebab9416dd6d7816c6859d44a71` on 2026-08-02. This file is retained
as implementation and verification evidence, not an active dispatch plan.

Bundle the canonical Inter and Space Grotesk web fonts in Argus so every build,
runtime, and browser QA path is offline with respect to font delivery.

Founder-locked 2026-08-02 for `codex/self-host-canonical-fonts`, targeting
`codex/private-alpha-next`.

## 1. Why

Argus's product truth prioritizes a clear, beginner-friendly chat experience
and supports English and Latin American Spanish (`docs/PRODUCT.md`, sections 2,
5, and 6). The design system assigns Inter to body/UI text and Space Grotesk to
display text (`.agent/designs/argus/DESIGN.md`, section 3). Self-hosting these
families removes a build-time and runtime dependency that can make the product
fall back or fail when Google Fonts is unavailable.

## 2. Locked decisions

1. Replace `next/font/google` with `next/font/local` in `web/app/layout.tsx`.
2. Keep the existing `--font-inter` and `--font-space-grotesk` CSS variables,
   existing ownership, supported weights, tracking, line heights, and locale
   behavior unchanged.
3. Bundle one Inter variable WOFF2 and one Space Grotesk variable WOFF2 from
   their authoritative upstream repositories, with no font CDN or new package.
4. Preserve all existing weights: Inter's current UI use must cover 400, 500,
   600, and 700; Space Grotesk must cover 300, 400, 500, 600, and 700.
5. Include standalone SIL Open Font License 1.1 notices and copyright/author
   attribution next to the bundled assets.
6. Prove English and `es-419` glyph coverage, local browser delivery, computed
   font ownership, and offline production build behavior with durable tests and
   exact-head provider-free Playwright evidence.

## 3. Reserved / parked scope

- Typography redesign, font-size/tracking/line-height changes, or component
  restyling -- the design contract is already locked.
- Italic font assets -- no current Argus declaration or rendered surface uses
  them, so adding them would increase payload without supporting this lane.
- API, schema, migration, provider, environment, feature-flag, or dependency
  changes -- this is a frontend asset/declaration correction only.
- Hosted QA, real authentication, chat prompts, backtests, and paid evals --
  this change is provider-free and does not touch runtime semantics.

## 4. Contract gates

- `web/app/layout.tsx` -- local font declarations and unchanged CSS-variable
  interface.
- `web/app/globals.css` -- must remain compatible with the existing variables;
  no design token change is expected.
- `web/app/fonts/*` -- canonical local WOFF2 assets and license evidence.
- `web/__tests__/font-contract.test.ts` -- source, asset, license, weight, and
  glyph regression coverage.
- No API contract, OpenAPI artifact, data model, schema, migration, package,
  environment, or feature-flag artifact changes.

## 5. Execution contract

- **PR shape:** one atomic PR, with the spec as its first commit and the font
  implementation/tests/assets in the delivery commit.
- **Proof required before the PR counts as ready:** focused font-contract tests,
  relevant existing frontend tests, the full frontend test suite, ESLint,
  TypeScript/production build with network blocked, `git diff --check`, any
  affected modularity/ownership gate, and exact-head provider-free Chromium
  desktop/mobile screenshots showing local font delivery and computed font
  ownership for English and Spanish strings.
- **Where it stops:** a posted PR targeting `codex/private-alpha-next`; the
  founder owns merge and deployment.

## 6. Stop conditions

- If either upstream family cannot be redistributed under a compatible license,
  pause for founder direction.
- If the selected local assets cannot cover all current weights or required
  English/`es-419` glyphs, pause for founder direction.
- If the smallest safe implementation requires changing the typography design,
  an API/schema/migration, hosted service, or deployment, pause.
- If a confirmed correctness or licensing problem remains unsolved within this
  bounded lane, report it rather than weakening the contract.

## Sources

### Argus authority

- `AGENTS.md`
- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `.agent/designs/argus/DESIGN.md`
- `docs/specs/private-alpha-next-roadmap.md`
- `docs/specs/private-alpha-next-decision-memo.md`

### External inspiration / provenance

- Inter 4.2 source and license: https://github.com/rsms/inter/tree/353b61b9f4430d5f420d56605a6e7993e0941470
- Space Grotesk 2.0.0 source and license: https://github.com/floriankarsten/space-grotesk/tree/7220f5d04813fe83babe76d4fd23e02275021280

### Inference

- A single variable upright WOFF2 per family is the smallest faithful web
  payload because the existing declarations only use upright weights and the
  variable files expose the full required weight ranges. This will be checked
  with font metadata and browser coverage tests before publication.
