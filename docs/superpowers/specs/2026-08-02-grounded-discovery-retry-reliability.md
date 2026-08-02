# Grounded Discovery Retry Reliability (#344)

Repair the three reproduced grounded-discovery failures without expanding the
approved discovery product or disguising unavailable provider configuration as
a recoverable user action.

Founder-locked 2026-08-02, after issue #344 consolidated checkpoint findings
S-02, S-05, and S-08 against the grounded-discovery baseline delivered through
PRs #276, #295, #298, and #300.

## 1. Why

Argus promises that discovery suggestions are either resolver-verified and
clearly marked as general knowledge or grounded in current sources. It also
promises that an accepted conversation turn makes useful progress or gives the
user an honest stopping point. Issue #344 shows both promises diverging from
the live experience: current-fact discovery failed in three forms, and every
visible Retry repeated the dead end.

This lane serves `docs/PRODUCT.md` section "Trust Through Clarity",
`docs/specs/private-alpha-interim-roadmap.md` outcomes 1 and 5, and
`docs/API_CONTRACT.md` section "Grounded Discovery Responses". It is a bounded
regression repair, not a reopened discovery program.

## 2. Locked decisions

1. Recent IPOs, trending cryptocurrencies, and explicit escalation from a
   general-knowledge discovery answer are already valid `asset_discovery`
   intents when current facts are required. This lane does not create a new
   discovery-category registry.
2. The exact prompts from S-02, S-05, and S-08 must enter the typed discovery
   route through the real interpreter. No regex, phrase gate, localized alias
   table, or pre-interpreter shortcut may be added.
3. Search configuration and authorization failures are not user-retryable.
   Missing configuration and HTTP 401/403 map to honest, non-retryable
   `discovery_unavailable` recovery.
4. Temporary provider failures remain retryable. Timeouts and other bounded
   transport/HTTP failures map to `discovery_search_failed`, and a subsequent
   replay of the same user request must succeed when the configured provider
   becomes available.
5. The configured provider remains the single provider for a turn. No
   automatic Perplexity-to-OpenRouter fallback chain is added; provider
   fallback remains explicitly deferred by the founder-approved discovery v1
   design.
6. The current worktree's default `perplexity_direct` adapter is present but
   returned HTTP 401 during diagnosis. That credential/configuration fact is
   external operational evidence, not a reason to weaken code or silently
   change the selected provider.
7. The existing `openrouter_web_search` adapter may be used only as a
   process-local acceptance surface when explicitly configured. A successful
   local override is not evidence that the default Perplexity configuration is
   healthy or deployed.
8. The general-to-grounded escalation turn must read as inferred user intent.
   It uses the sidecar's resolver-validated candidate asset classes to produce
   localized, semantic text such as "Search for current stocks in the
   pharmaceutical sector". Uniform equity, crypto, and currency-pair sets use
   their matching noun; mixed sets use the generic "assets" noun.
9. The escalation remains an ordinary natural-language user turn. It does not
   become a typed action, bypass the interpreter, mutate a pending draft, or
   add a second runtime owner.
10. English and Latin American Spanish receive equivalent escalation meaning,
    retry availability, and recovery truth.
11. Mocked and regression suites prove only deterministic code paths. They do
    not satisfy acceptance by themselves.
12. Before mandatory review, the exact worker head must pass the live
    interpreter eval for the issue prompts and bilingual real-API browser QA.
    Evidence must name the exact SHA, runtime/provider configuration, and
    observed typed route and user-visible outcome.
13. The lane stops at an open PR targeting `codex/private-alpha-next`. The
    founder owns merge, hosted secret changes, deployment, and tester exposure.

## 3. Reserved / parked scope

- Automatic provider fallback chains -- explicitly deferred by the approved
  discovery v1 design; adding one would reopen provider selection, latency,
  freshness, and cost decisions.
- Rotating or editing hosted/local shared provider secrets -- operational
  authority outside this worker PR. Shared linked `.env` files remain
  read-only.
- Earnings, corporate events, central-bank actions, news research, or general
  Research Lab behavior -- separate future product slices with their own typed
  owners and freshness contracts.
- Discovery UI redesign, candidate-row presentation, sources drawer, or
  resolver policy -- checkpoint evidence says those surfaces are already
  correct and issue #344 marks them no-touch.
- New persistence tables, RLS policies, quota semantics, provider selection,
  or public API endpoints -- unnecessary for this repair.
- Automatic execution after discovery -- selection and escalation continue
  through the ordinary interpreter and confirmation lifecycle.

## 4. Contract gates

- `docs/API_CONTRACT.md` -- clarify that missing/unauthorized Search
  configuration emits non-retryable `discovery_unavailable`, while temporary
  provider failures emit retryable `discovery_search_failed`.
- `docs/superpowers/specs/2026-07-25-grounded-discovery-search-v1-design.md` --
  append a narrow issue #344 reconciliation note only if implementation truth
  would otherwise conflict with its outage table; do not rewrite its historical
  provider-selection record.
- OpenAPI artifact -- no regeneration expected because this lane does not
  change a public request/response schema or endpoint.
- `docs/DATA_MODEL.md` -- no change expected; messages, recovery metadata,
  lifecycle state, and discovery accounting retain their current contracts.
- `tests/evals/measurement_cases/asset_discovery_routing.yaml` and its harness
  -- add the exact issue prompts and assert `needs_current_facts` in typed
  interpreter output.
- `web/public/locales/en/common.json` and
  `web/public/locales/es-419/common.json` -- keep static escalation copy in
  parity and derive behavior from typed asset classes, never translated labels.

## 5. Execution contract

- **PR shape:** one worker PR targeting `codex/private-alpha-next`. The spec is
  the first commit; implementation and evidence may use later focused commits
  inside the same PR.
- **Original integration base:**
  `6533377c1a08539136a622a7d53eee20d0efd845`, fetched from
  `origin/codex/private-alpha-next` on 2026-08-02.
- **Required deterministic proof:** test-first red/green coverage for HTTP
  401/403 classification, missing configuration, temporary provider failure,
  fail-then-succeed Retry, escalation asset-class inference, EN/es-419 copy,
  exact discovery-route cases, and unchanged zero-Search controls. Run the
  focused suites, mocked eval harness, hermetic agent-runtime sweep, frontend
  tests, lint/type checks, and any affected full backend/frontend gate.
- **Required live interpreter proof:** once, pre-review, on the exact candidate
  SHA under the sanctioned live-eval command. The exact S-02, S-05, and
  semantic S-08 prompts must produce `semantic_turn_act=asset_discovery`, the
  expected asset-class hint/category, and `needs_current_facts=true`. Mocked or
  injected interpretations are not substitutes.
- **Required bilingual browser proof:** real API, English and es-419, on the
  same exact candidate SHA. Prove one current equity category journey, one
  current crypto category journey, general-knowledge-to-current escalation,
  non-retryable unavailable configuration, and fail-then-succeed Retry when a
  provider is genuinely available. Capture sanitized screenshots/evidence;
  record provider/runtime mode and do not expose secrets.
- **Review gate:** complete a mandatory independent Argus code review against
  the exact candidate diff after live and browser evidence pass. Address only
  validated, proportional findings, then rerun any evidence invalidated by the
  fix before opening the PR.
- **Integration freshness:** fetch `origin/codex/private-alpha-next` before the
  READY claim, record original and current integration SHAs, reconcile one-way
  if integration advanced, and assess semantic overlap before deciding which
  live evidence remains valid.
- **Where it stops:** push the worker branch and open the reviewed PR. Do not
  merge, change hosted configuration, deploy, apply migrations, expose testers,
  or close issue #344 as part of this lane.

## 6. Stop conditions

- If the exact live interpreter does not type one of the three prompts as
  `asset_discovery`, stop and report the typed output and route receipts rather
  than adding deterministic phrase logic.
- If recent-IPO support proves to require a new capability/category registry
  rather than the existing typed current-fact contract, stop for a separate
  founder approval gate.
- If acceptance requires an automatic provider fallback chain or changes the
  founder-selected default provider, stop and report; that is reserved scope.
- If no explicitly configured provider is usable for live/browser acceptance,
  stop with the external-capability evidence. Do not label mocked tests as live
  proof.
- If the only path to bilingual browser proof needs hosted/destructive writes,
  production credentials, shared `.env` mutation, or unbounded provider spend,
  stop and request authority.
- If the smallest safe fix requires discovery UI/presentation redesign, new
  persistence/RLS, quota changes, or a second chat runtime, stop and report the
  architecture expansion.
- If integration advances with semantic overlap in interpreter routing,
  recovery ownership, provider selection, discovery sidecars, or chat action
  presentation, reconcile and invalidate only the affected evidence before
  review.

## Sources

### Argus authority

- `AGENTS.md`
- `docs/PRODUCT.md` -- Trust Through Clarity and Honest Boundaries
- `docs/ARCHITECTURE.md` -- one LLM-owned interpretation layer, deterministic
  post-interpretation guardrails, and failure handling
- `docs/API_CONTRACT.md` -- Structured Action Semantics and Grounded Discovery
  Responses
- `docs/DATA_MODEL.md` -- message recovery/discovery metadata and lifecycle
  ownership
- `.agent/designs/argus/DESIGN.md` -- chat-first next moves and bilingual UX
- `docs/specs/private-alpha-interim-roadmap.md` -- outcomes 1 and 5
- `docs/specs/private-alpha-next-roadmap.md` -- interpreter-facing live gate
- `docs/specs/private-alpha-next-decision-memo.md` -- Search only when freshness
  matters and failure/recovery trust
- `docs/reports/2026-08-01-current-checkpoint-experience-feedback.md` -- locked
  S-02, S-05, and S-08 evidence plus founder addendum
- `docs/superpowers/specs/2026-07-25-grounded-discovery-search-v1-design.md` --
  approved single-provider and fallback-defer boundaries
- GitHub issue #344

### External inspiration

- None. This repair follows existing Argus contracts and current provider
  adapters.

### Inference

- The current Perplexity 401 reproduces a provider-authorization boundary but
  cannot by itself prove the original checkpoint request's typed interpreter
  output. Exact-head live eval supplies that missing proof.
- The S-05/S-08 compact copy identifies an interpreter-unavailable recovery
  family, but route/provider causality must be verified from typed live output
  rather than inferred from prose alone.
- Resolver-validated candidate classes are sufficient to choose semantic
  escalation nouns without adding a backend field; a mixed-class set safely
  falls back to the generic asset noun.
