# Argus Result Voice Bridge Design

Status: Approved design checkpoint
Date: 2026-06-11
Branch: `codex/private-alpha-next`
Audience: Founder, Codex, reviewers

## Purpose

Clean up the current private-alpha result voice without pretending this is the
final Argus research loop.

Quick take and Explain result remain core surfaces. They should feel like two
natural, non-overlapping turns from the same LLM brain: a first-glance result
readout and a deeper fact-grounded explanation. The visible Try next action is
removed from the current result surface because upcoming Research Lab and
milestone-loop work should own deeper next-step reasoning.

This is a bridge contract. It keeps today's web app honest, useful, and
replaceable while preserving room for the later 0-to-8 / 8-to-0 product loop.

## Product Decisions

- Keep **Quick take**.
- Keep **Explain result**.
- Remove **Try next** as a visible result action or CTA.
- Do not polish Try next as a destination product surface.
- If a user manually asks what they should try next, answer through the backend
  LLM follow-up path, grounded in result facts, supported capabilities, and the
  current conversation state.
- Deterministic code supplies facts, constraints, provenance, fallback safety,
  and metadata. It must not become the normal happy-path Argus voice.

## Prompting Principle

The Perplexity Agent API prompt guide is useful as a design reference, not as an
integration requirement:
https://docs.perplexity.ai/docs/agent-api/prompt-guide

The relevant lesson is to keep durable role, tone, and grounding rules in
backend instructions; keep the user's actual question as the input; and express
hard constraints through structured fields, schema, and runtime parameters
rather than relying on long prose instructions.

For Argus, that means:

- LLM prompts should be concise and reusable.
- The fact bank should carry canonical result truth, supported actions, caveats,
  and capability limits.
- Structured schemas should capture hard requirements such as fact IDs,
  supported next-test option kinds, source metadata, and causality claims.
- The model should be allowed to say when the facts do not support an answer
  instead of filling gaps with generic advice.

## Current Shape

- `src/argus/agent_runtime/stages/explain.py` owns Quick take generation and
  result-readout fallback provenance.
- `src/argus/api/chat/breakdown.py` owns Explain result generation and fallback
  behavior.
- `src/argus/agent_runtime/result_followups.py` owns typed result follow-ups,
  including current next-experiment focus handling.
- Result cards expose card-scoped actions in the web app.
- Result readout and breakdown metadata already expose source and fallback
  flags.

The current branch already has some useful guardrails: Quick take avoids
rendering supported next experiments as visible "Try next" prose, Explain result
rejects Quick take / Quick breakdown framing, and fallback metadata is
observable. This slice should reinforce those boundaries and remove the
redundant visible Try next action.

## Voice Model

### Quick Take

Quick take is the first useful read after a completed result.

It should:

- be LLM-authored in the happy path;
- be short and beginner-friendly;
- name the main result, comparison, and caveat when those facts exist;
- avoid turning into a mini report;
- avoid visible next-step guidance beyond what is needed to understand the
  result.

### Explain Result

Explain result is the deeper result explanation when the user asks for it.

It should:

- be LLM-authored in the happy path;
- use fact-grounded sections or short blocks;
- explain setup, interpretation, benchmark comparison, risk or drawdown,
  assumptions, and caveats;
- avoid reusing Quick take, Quick breakdown, or first-glance framing;
- avoid unsupported causality, predictions, investment advice, and provider
  plumbing.

### Typed "What Should I Try Next?"

Typed next-step questions are normal conversation, not a visible result CTA.

They should:

- route through the backend LLM follow-up path;
- use the current result and supported capability facts as grounding;
- offer modest supported next tests only when the fact bank includes them;
- avoid claiming a strategic research path or future Research Lab behavior;
- say clearly when Argus cannot support the requested next test today.

## Goals

- Remove the visible Try next action from result surfaces.
- Preserve Quick take and Explain result as separate, complementary surfaces.
- Keep typed next-step follow-ups LLM-owned and grounded.
- Keep deterministic fallback copy observable through metadata and route
  receipts.
- Add focused tests that protect surface ownership without freezing exact
  wording.
- Keep this slice small enough to finish before Research Lab product-spec work.

## Non-Goals

- No Research Lab implementation.
- No Perplexity Agent API integration.
- No citations, web research, inbox briefs, saved research, or monitoring.
- No final Argus voice system for future milestones.
- No deterministic happy-path result prose expansion.
- No frontend-generated result explanation.
- No broad rewrite of LangGraph interpretation, execution, or artifact
  lifecycle.
- No mobile-specific work.

## Data Flow

```text
Completed result
  -> canonical result facts and result card
  -> Quick take LLM schema
  -> result readout metadata: source, fallback_used, failure_mode
  -> result card shows Explain result action only

User clicks Explain result
  -> canonical result context / fact bank
  -> Explain result LLM schema
  -> breakdown metadata: source, fallback_used, failure_mode

User types "what should I try next?"
  -> LangGraph interpretation against latest result artifact
  -> result follow-up fact bank and supported capability facts
  -> backend LLM follow-up answer
  -> fallback only if LLM path is unavailable or rejected
```

## Error Handling

- If Quick take LLM generation fails or the draft violates facts, use the
  existing deterministic fallback and mark fallback provenance.
- If Explain result LLM generation fails or references invalid facts, use the
  existing grounded fallback and mark fallback provenance.
- If a typed next-step follow-up lacks supported next-test facts, the response
  should say what can be adjusted in supported terms or ask a clarifying
  question. It should not invent Research Lab behavior.
- Existing source and fallback metadata must remain available for tests, route
  receipts, and live readiness gates.

## Testing

Focused tests should cover:

- Result cards do not expose a visible Try next action.
- Explain result remains available.
- Quick take does not render visible Try next sections or generic next-step
  advice.
- Explain result does not use Quick take / Quick breakdown headings.
- Typed next-step follow-ups use the LLM follow-up path and supported fact bank
  constraints.
- Next-step follow-up fallback remains observable as fallback, not a happy-path
  result voice.
- Existing result-readout source and fallback metadata remain intact.

The tests should assert semantic boundaries and action ownership, not exact
phrasing except where exact labels define the product surface.

## Acceptance Criteria

- The visible result action set no longer includes Try next.
- Quick take and Explain result remain present and distinct.
- A typed "what should I try next?" follow-up can still be answered by the
  backend LLM path when grounded by result facts.
- Deterministic fallback language remains metadata-visible.
- No Research Lab or Perplexity integration is introduced.
- Focused backend and frontend tests pass.
- `git diff --check` passes.
