# Confirmation card summary prose: evidence

Evidence for PR #618. Test results are in the CI run linked from the PR
description. The live route check is in `route-check/README.md`.

## Browser replay

### What ran

- `replay_confirmation_api.py` served the API on memory persistence, mock auth
  and the synthetic market-data fixture, with the keys its docstring lists
  removed from its environment. It seeded `es-419` conversations through the
  card builder and `create_message`: buy-and-hold, recurring-buys and RSI
  threshold card turns, and a legacy buy-and-hold card turn stored the old way
  its docstring describes.
- `capture_confirmation_evidence.mjs` opened each conversation in headless
  Chromium against the web app on that API and saved a screenshot and the
  `/messages` response for each. It then called the in-place edit endpoint once,
  captured that conversation again, and saved the conversation list and a
  search for AAPL.
- `before/` was captured at the head recorded in `before/replay-manifest.json`,
  and `after/` at the head recorded in `after/capture-report.json`.

### Files

- `after/capture-report.json`: for each capture, the page's `lang`, its visible
  text, whether the page HTML or the whole `/messages` response contains
  `Ready to test`, the card turn's content, and each path to a
  `confirmation_card` or `confirmation` object that carries `summary`; the
  status, content and same scan of the in-place edit response; and the console
  errors the page logged.
- `after/*.png` and `after/*-messages.json`: the screenshot and `/messages`
  response for each capture.
- `after/conversations.json` and `after/search-aapl.json`: the conversation
  list and the search response.
- `after/thread-history.json`: for each conversation, the stored content,
  whether the stored card carries `summary`, the stored preview, the loaded
  thread history, and the assistant line artifact naming reads.
- `before/`: the replay manifest, the conversation list, the `/messages`
  responses and the thread history for three conversations.

### Known gaps

- The replay seeds card turns directly; no chat turn was sent.
- Provider and database access are not recorded, and Argus loads a
  repository-root `.env` at import without overriding set values.
- No committed script writes the files in `before/` or
  `after/thread-history.json`. `before/` has no screenshots, no capture report
  and no legacy conversation.
- The after replay's manifest, which records working tree changes under `src`
  and `web`, was written to `temp/` and not committed.

### Reproduce

From the repository root with the backend environment active:

```bash
python docs/reports/evidence/confirmation-summary-prose/replay_confirmation_api.py
```

```bash
cd web && NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8593/api/v1 NEXT_PUBLIC_MOCK_AUTH=true NEXT_PUBLIC_ENABLE_SPANISH=true NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321 NEXT_PUBLIC_SUPABASE_ANON_KEY=replay-local-anon bun run dev -- --hostname 127.0.0.1 --port 3293
```

```bash
node docs/reports/evidence/confirmation-summary-prose/capture_confirmation_evidence.mjs
```

The replay writes `temp/replay-manifest.json` and the capture writes
`temp/evidence-after/`, both under the repository root.
