# Business pilot local end-to-end harness (preserved, not product code)

This folder is preserved for the Business lane handoff. It was the scratch harness behind the local B1 evidence under `docs/reports/evidence/cuadrao-business-owner-pilot/` (for example `2026-10-08-isolation-e2e/` and `2026-10-08-b1-rerun/`). It is not imported by the app or by the test suite, and CI does not run it.

## What it does

- `launcher.py` starts the real API against a local Supabase stack, with two seams replaced:
  - a stub document extractor, so no model is called;
  - local WhatsApp media files, so Meta is never reached.

  Outbound proxies point at a dead local port. `ISO_FLAG_OFF=1` starts it with the Business flag unset.
- `api.sh` and `web.sh` start and stop the API and web on local ports.
- `users.py` creates two synthetic owners through the local admin API, with random passwords generated at run time.
- `journey.mjs`, `search.mjs` and `flagoff.mjs` are the Playwright journeys. `counts.py` reads row counts.
- `make_receipts.py` generates the SAMPLE DATA receipt images. `media/` holds the local WhatsApp media.

## Not included

These were excluded on purpose, and regenerate them locally:
- `stack.env`: the output of `supabase status -o env` for your local stack.
- `users.env`: written by `users.py`.
- `wa.env`: local WhatsApp fixture settings.
- All logs and run outputs.

## Caveats

- Paths in `api.sh` and `web.sh`, and the stack guard in `users.py`, are hard-coded to the original machine and to a stack named `argus-biz-spaces` (API port 57781, DB 57782). Adjust them before use.
- Use only a disposable local stack. Never point it at hosted Supabase, and never set provider keys.
