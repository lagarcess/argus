# Issue #453: Cause-aware strategy refusal recovery

Route strategy turns by their typed failure cause so Argus never exposes raw
interpreter output, refuses supported dollar-cost averaging, describes a bounds
violation as a capability gap, or acknowledges a value before rejecting it.

Founder-locked 2026-08-12 from production guest transcripts
`e8ce8265-e78d-42ce-b122-871b05bd21a2`,
`69d9914e-17e0-4ed7-b699-4419f3ef4bf0`, and
`4494321e-ad2a-4e7f-b3ec-40485e1f5830` in issue #453.

## 1. Why

The conversation is Argus's primary product surface, and the Golden Path is a
first successful backtest. `docs/PRODUCT.md` requires the assistant to help a
normal person structure and simulate an idea without invented or misleading
facts. `docs/CONVERSATIONAL_RUNTIME.md` assigns natural-language interpretation
to the LLM and capability and execution validation to deterministic runtime
guards. A raw model summary in localized prose, or a capability refusal for a
supported strategy or numeric bound, breaks both contracts and user trust.

## 2. Locked decisions

1. A generic unsupported-strategy recovery may describe only a typed capability
   cause. It must never render an interpreter `raw_value`, goal summary,
   explanation sentence, or user phrase as the grammatical subject.
2. Remove the generic locale variants
   `chat.clarification.unsupported_recovery_with_raw_value` and
   `chat.clarification.unsupported_recovery_with_raw_value_for_asset` in English
   and Spanish. Typed special cases such as bar size and future-performance
   recovery keep their dedicated messages.
3. Plain recurring fixed-dollar purchases over time are
   `dca_accumulation`, a supported first-class strategy. A contradictory model
   unsupported verdict must be repaired through the existing typed capability
   audit and admitted to ordinary required-field or confirmation handling.
4. Starting capital validation runs before any confirmation or acknowledgment.
   Non-DCA starting capital below `MIN_STARTING_CAPITAL` routes to the existing
   `invalid_starting_capital` launch-validation recovery, which names the
   canonical minimum and maximum. DCA recurring contributions retain their
   existing positive-value rule.
5. When an unsupported verdict survives admission, model-authored
   `assistant_response` is suppressed. The clarification stage owns the
   cause-aware response and cannot repeat an acknowledgment that was not
   validated.
6. Bounds violations, unsupported capabilities, and incomplete or unparseable
   extraction remain distinct typed outcomes. Only the capability outcome says
   that Argus cannot run a strategy.
7. The runtime stays LLM-first. This lane adds no regex, language-specific
   phrase table, localized alias, or alternate intent router.
8. English and es-419 use the same backend causes and maintain locale parity.
   New user copy contains no em dash.

## 3. Reserved / parked scope

- Research synthesis missing-subject recovery is owned by issue #457. This lane
  does not create a cross-domain rendering helper or modify research files.
- Provider, release, deployment, and environment configuration are unchanged.
  In particular, do not edit `render.yaml`, `.env.example`,
  `.github/argus-env.sh`, the release profile, `.env`, or `web/.env.local`.
- No capability expansion beyond already executable strategy families is part
  of this fix.
- No production deploy or merge is authorized. The founder retains both.

## 4. Contract gates

- `docs/API_CONTRACT.md` - document cause-aware unsupported recovery projection,
  remove the generic raw-value example, and preserve typed recovery payloads.
- `docs/DATA_MODEL.md` - no persistence or schema change is expected.
- OpenAPI - regenerate only if implementation changes an API schema. A metadata
  projection-only change does not require regeneration.
- English and es-419 locale catalogs - remove only the two generic raw-value
  variants and preserve the union of additive changes from the parallel
  research lane.

## 5. Execution contract

- **PR shape:** one focused PR against `codex/private-alpha-next`, based on
  `8025672924d1c74eb80cc926c72b5d8574b613d7`, delivering all four production
  defects. The lane branch is `codex/issue-453-unsupported-refusal`.
- **Proof required before the PR counts as ready:** record all four defects on
  the untouched base, add backend and web regressions first, pass focused tests,
  the full backend and web suites, Ruff, formatting, the mocked interpreter
  harness, and the modularity budget against the would-be merged tree. Capture
  durable bilingual EN and es-419 browser proof through the guest path at the
  exact final head. The proof must show the supported DCA route, the explicit
  `$1,000` floor for a `$500` buy-and-hold request, no raw interpreter phrase,
  and no premature acknowledgment.
- **Review:** run the repository review workflow and the GitHub review loop until
  the latest fix delta receives a clean verdict and the PR has zero unresolved
  review threads. Do not request review again on an unchanged head.
- **Where it stops:** at an open, reviewed, CI-terminal PR. The founder merges
  and directs any deployment.

## 6. Stop conditions

- If the fix requires a language-specific parser, a second chat brain, or a new
  generic cross-domain rendering framework, stop and report to the founder.
- If the exact guest browser path cannot be exercised without modifying a
  forbidden environment file or dispatching paid Render work, stop and report
  the evidence limitation rather than weakening the boundary.
- If current `origin/codex/private-alpha-next` changes a shared runtime owner or
  locale key used by this lane, reconcile one-way, audit semantic overlap, and
  stop for founder direction if the two contracts cannot be preserved as a
  union.
- If a confirmed correctness fix exceeds this issue's recovery, admission, or
  launch-validation boundaries, stop and spin the finding into separately owned
  scope.

## Sources

### Argus authority

- `AGENTS.md`
- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `docs/CONVERSATIONAL_RUNTIME.md`
- `.agent/designs/argus/DESIGN.md`
- `docs/specs/argus-active-roadmap.md`
- `docs/specs/private-alpha-next-decision-memo.md`
- GitHub issue #453 and its three production transcript identifiers

### External inspiration

- None.

### Inference

- The four symptoms share one causal seam: an unsupported model verdict reaches
  admission before deterministic launch validation, and its untyped summary can
  become both response prose and recovery metadata. The implementation must
  preserve typed capability audits while making display projection fail closed.
