# Asset Discovery Quality Design

Status: Approved design checkpoint
Date: 2026-06-11
Branch: `codex/private-alpha-next`
Audience: Founder, Codex, reviewers

## Purpose

Improve private-alpha `@` discovery so it feels faster and returns more
predictable provider-backed matches for supported assets and runnable
indicators, without changing how chat interpretation works.

Selected mentions remain provenance only. They can help preserve the user's
chosen asset identity, but they must not bypass LangGraph interpretation,
backend resolution, capability checks, same-asset validation, or execution
guardrails.

## Current Shape

- `web/components/chat/ChatInput.tsx` owns the composer discovery picker.
- `web/lib/argus-api.ts` calls `/discovery/assets` and
  `/discovery/indicators`, with a browser-session cache.
- `src/argus/api/routers/discovery.py` exposes discovery responses.
- `src/argus/domain/market_data/assets.py` owns provider-backed asset search.
- `src/argus/domain/indicators.py` owns indicator search and executable
  indicator status.

The existing system already avoids the old static preview catalog, filters
indicator discovery to supported indicators, and keeps selected mentions as
optional chat request provenance.

## Goals

- Improve provider-backed asset ranking for ticker, company-name prefix, common
  crypto pair, and currency-pair searches.
- Preserve strict behavior for typo-like ticker queries: do not promote close
  matches as provider truth.
- Improve perceived speed by avoiding unnecessary result clearing/flicker for
  cached or repeated discovery searches.
- Keep discovery result labels and descriptions beginner-friendly without
  exposing provider plumbing in assistant-facing copy.
- Add focused tests that make the ranking and perceived-speed contract explicit.

## Non-Goals

- No Supabase-backed discovery cache.
- No market-data cache schema, freshness policy, or invalidation policy.
- No embeddings, pgvector, semantic search, or RAG.
- No static company hint table.
- No fuzzy typo correction for ticker-like inputs.
- No unsupported indicator discovery in the private-alpha composer.
- No changes to execution semantics, asset validation, or LangGraph routing.

## Recommended Approach

Use a narrow quality pass across the existing seams:

1. Backend asset search:
   - Tighten provider-backed scoring in `search_assets`.
   - Rank exact ticker and exact alias first, then symbol prefix, then name
     prefix, then contained matches.
   - Add stable tie-breakers that prefer direct provider assets over wrapper ETF
     noise when the query is clearly a company or asset prefix.
   - Keep typo-like ticker queries strict.

2. Composer merge/ranking:
   - Keep the separate asset and indicator endpoints for now.
   - Refine `mergeDiscoveryItems` so exact runnable indicators can still win
     when the user types a true indicator name, while asset-like ticker/company
     searches prioritize assets.
   - Avoid small result caps that make provider-backed catalogs feel artificially
     tiny.

3. Perceived speed:
   - Do not clear existing results immediately for a new query if a search is
     already visible. Let the panel show loading while preserving the last
     usable results until fresh results arrive or the query becomes empty.
   - Keep failed searches non-sticky so a later provider recovery can succeed.

## Data Flow

```text
Composer input
  -> ChatInput discovery query
  -> searchDiscovery("assets" | "indicators")
  -> /api/v1/discovery/assets and /api/v1/discovery/indicators
  -> provider-backed asset catalog / executable indicator catalog
  -> merged picker results
  -> selected token metadata in ChatMention[]
  -> chat stream request mentions provenance
  -> LangGraph interpretation and backend validation
```

## Error Handling

- Empty query returns the normal invitation state.
- Partial provider failure can still show results from the other source.
- Full provider failure shows the existing "discovery unavailable" copy and does
  not block plain-text chat submission.
- A selected mention with stale or invalid metadata must still be validated by
  backend interpretation and resolution.

## Testing

Focused tests should cover:

- Asset search ranking for exact ticker, symbol prefix, provider name prefix,
  crypto pair aliases, and currency-pair aliases.
- No promotion of close ticker typos.
- Discovery endpoint response shape and provider/source preservation.
- Composer merge behavior for asset-like and indicator-like queries.
- Composer loading behavior that preserves visible results during an in-flight
  follow-up query.
- Existing cache behavior: dedupe successful repeated queries, do not cache
  failures.

## Acceptance Criteria

- Common `@` searches rank predictably without adding static hints or fuzzy typo
  correction.
- The picker feels less jumpy during repeated/incremental searches.
- Supported indicators remain discoverable and unsupported indicators stay out
  of the private-alpha picker.
- Selected mentions still serialize as provenance only.
- Local focused frontend and backend discovery tests pass.
- `git diff --check` passes.
