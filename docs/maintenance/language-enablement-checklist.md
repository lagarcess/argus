# Language Enablement Checklist

Use this checklist when adding or enabling a new Argus language. Keep it
practical: language support is a product/runtime capability, not only a locale
file.

## Language vs. Locale

- **Language** controls user-facing prose: static UI copy, assistant responses,
  onboarding text, and explanatory result language.
- **Locale** controls formatting: dates, numbers, currency, compact ranges, and
  culturally appropriate display labels.
- Persist both. Current Alpha values are `language: en | es-419` and
  `locale: en-US | es-419`.

## Current Source of Truth

- `profiles.language` and `profiles.locale` are the durable user preference.
- `conversations.language` may preserve thread continuity, but profile language
  remains the primary preference.
- Frontend i18next resources live in `web/public/locales/<language>/common.json`.
- Enabled frontend languages are defined in `web/lib/language-features.ts`.
- Spanish is registered behind `NEXT_PUBLIC_ENABLE_SPANISH`; do not claim it is
  production-ready just because a locale file exists.

## Current Spanish Readiness Decision

Spanish work on `codex/private-alpha-next-jules-intake` is **scaffolding only**
until a separate Codex-owned runtime readiness gate passes. The branch may add
locale files, stable translation keys, documentation, and static UI tests, but
it must not be treated as a release signal for Spanish private-alpha users.

Keep `NEXT_PUBLIC_ENABLE_SPANISH` disabled in production-like Render
environments until all of these pass:

- Spanish static UI smoke for the private-alpha surfaces.
- Spanish production-parity chat QA covering at least one multi-turn
  clarification and confirmation flow.
- Spanish result/job/retry/recovery surfaces render without English happy-path
  or failure copy leaking into the user-facing transcript.
- A live or local QA canary verifies that structured runtime state survives
  continuation turns without depending on translated labels as executable truth.

The current known blocker is runtime-state normalization in Spanish
continuation flows. A Spanish user can reach paths where serialized
`resolution_provenance` entries rehydrate as dictionaries while runtime helpers
expect model objects. That is a language-readiness blocker because it exposes
that the chat/backtest spine is not yet fully presentation-language agnostic.
Fixing this belongs to Codex-owned runtime work, not mechanical locale intake.

## Frontend Responsibilities

- Add the locale directory and keep JSON key/placeholder parity with `en`.
- Add the language to `ALL_LANGUAGES` and gate it with an explicit public feature
  flag until release-ready.
- Use `localeForLanguage()` or an equivalent central helper for formatting.
- Keep static UI strings in i18next. Avoid new hardcoded fallbacks unless they
  are temporary and tracked.
- Use structured artifact keys/statuses for behavior. Do not treat translated
  labels as durable truth.
- Verify settings/profile language changes patch `/me` with both `language` and
  matching `locale`.

## Backend Responsibilities

- Validate supported `language` and `locale` through API schemas/contracts before
  accepting profile updates.
- Resolve chat response language in this order: explicit request language,
  profile language, then English fallback.
- Pass resolved language into the LangGraph runtime, naming, result readout, and
  artifact builders that own user-facing prose.
- Return structured artifact facts, statuses, and action types. Translate labels
  at the presentation edge where possible.
- Keep provider names, route receipts, model metadata, and internal enum names out
  of assistant-facing copy.

## LLM Responsibilities

- Generate natural prose in the selected language unless the user explicitly asks
  for another language in-message.
- Preserve Argus voice: beginner-friendly, precise, honest about assumptions, and
  free of provider plumbing.
- Keep prompts and internal system instructions in the language that makes the
  runtime safest and most reproducible. Translating prompt contracts is Codex-owned
  runtime work, not a mechanical Jules task.
- Use deterministic fallbacks only as explicit recovery behavior, never as the
  normal happy path for Argus voice.

## Artifact Guidance

- Store facts, status codes, run ids, action types, symbols, dates, and metrics as
  structured data.
- Store user-facing labels as renderable copy, not as the source of executable
  truth.
- Avoid string matching on translated labels. If a component needs behavior,
  introduce a stable key or enum.
- Result cards, confirmation cards, queued/running cards, Quick take, Explain
  result, and Try next must preserve their current ownership boundaries.

## Release Checklist

Before enabling a language flag in Render:

- Locale JSON is valid and has key/placeholder parity with `en`.
- Static UI smoke covers onboarding, chat, settings/profile, confirmation cards,
  queued/running cards, result cards, feedback/retry/more-menu actions, and
  archived/deleted chat surfaces.
- Profile update QA confirms language and locale persist through `/me`.
- Production-parity chat QA confirms assistant prose follows the selected
  language while still honoring Argus voice.
- Live canary passes before inviting users in that language.
- Rollback is simple: turn the public language flag off without a migration.

## Ownership

**Jules-safe**

- Locale JSON key/placeholder parity.
- Static UI copy inventory and mechanical i18next migrations.
- Docs that describe current implementation without changing runtime behavior.
- Narrow tests that fail on missing locale files, keys, placeholders, or feature
  flag drift.
- Static UI i18n migrations that do not alter LangGraph state, backend runtime
  semantics, provider resolution, or user-facing assistant prose generation.

**Codex-owned / product-runtime**

- LangGraph prompt, interpreter, clarification, explanation, and result voice
  changes.
- Backend language resolution semantics.
- Structured artifact contract changes.
- Runtime state normalization and hydration across continuation turns.
- Recovery/failure copy policy for non-English conversations.
- Per-language live/local canaries that exercise real chat interpretation,
  confirmation, queued/running/result jobs, retry actions, and reload hydration.
- Anything that touches Supabase migrations, auth/RLS, Render env/config, model
  provider plumbing, backtest engine semantics, or private-alpha release gates.

## Follow-Up Recommendations

- Use `docs/maintenance/spanish-readiness-inventory.md` as the first migration
  backlog for Spanish-specific gaps.
- Prefer fixing string-as-state behavior before adding more languages.
- Add a small language QA transcript set once Spanish private-alpha behavior is
  human-approved.
