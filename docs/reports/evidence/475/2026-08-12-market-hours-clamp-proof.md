# #475 Market-Hours Completion-Clamp Proof — 2026-08-12

Both runs below executed against the live Alpaca provider during the same US
market session (Wednesday 2026-08-12), with `ENABLE_MARKET_DATA_CACHE=false`,
using the exact request from the failed production job `69093c56-f699-4309-b289-6fb3df39f069`
(conversation `309b0ad6-309d-4976-a2f0-8cb5b82650e5`): KO, 1D, 2021-08-12 →
2026-08-12, benchmark SPY.

## Run A: pre-fix behavior, 16:44Z (12:44 ET, market open)

Two identical `prepare_market_data` fetches ~30 seconds apart on the pre-fix
coverage path (production `d67cef92` and lane base `c3a9aca1` are byte-identical
here). Today's forming bar is included and moves between fetches, so the
dataset hashes cannot match; production's worker-side
`_validate_approved_window` therefore rejects every such run with
`approved_data_window_unavailable`.

```
fetch_1  effective 2021-08-12..2026-08-12  KO 1254 / SPY 1255 bars
         ko_last_index 2026-08-12 04:00:00+00:00 (forming)
         ko_last_bar close 87.025  volume 417972
         dataset_id sha256:03fc69c302313a496dfd25f85f57ca46837295237787d60236beabf8bdb8b5cc

fetch_2  effective 2021-08-12..2026-08-12  KO 1254 / SPY 1255 bars
         ko_last_index 2026-08-12 04:00:00+00:00 (forming)
         ko_last_bar close 86.995  volume 419452
         dataset_id sha256:5b14ca75e2769d18e35ede923484dda5c964408f7288fd8289e824ba1fc0dada

HASHES_EQUAL: False
```

## Run B: post-fix behavior, 17:03Z (13:03 ET, market open)

Same request through the full production mechanism: fetch 1 plays the
confirmation preflight, fetch 2 plays the worker ~30 seconds later and consumes
fetch 1's approved coverage payload, so `_validate_approved_window` runs
exactly as production runs it.

```
preflight  at 2026-08-12T17:03:14Z
           outcome adjusted_coverage  reason calendar_alignment
           requested 2021-08-12..2026-08-12  effective 2021-08-12..2026-08-11
           KO 1253 / SPY 1254 bars
           ko_last_index 2026-08-11 04:00:00+00:00 (final)  ko_last_close 86.505
           dataset_id sha256:0649d30f8622777a6355ab09c8c24256928f758ad21580cef87df130ad8fedee

worker     at 2026-08-12T17:03:45Z
           outcome adjusted_coverage  reason calendar_alignment
           requested 2021-08-12..2026-08-12  effective 2021-08-12..2026-08-11
           KO 1253 / SPY 1254 bars
           ko_last_index 2026-08-11 04:00:00+00:00 (final)  ko_last_close 86.505
           dataset_id sha256:0649d30f8622777a6355ab09c8c24256928f758ad21580cef87df130ad8fedee

EFFECTIVE_WINDOWS_EQUAL: True
HASHES_EQUAL: True
APPROVED_WINDOW_VALIDATION: passed (no MarketDataCoverageError raised)
```

## Reading

- The clamp removed exactly one bar per series relative to Run A (KO 1254→1253,
  SPY 1255→1254): today's forming bar.
- The effective window now ends at the last completed session (2026-08-11), the
  confirmation card's data-through label renders that honestly, and the
  byte-identity integrity check is untouched and passes because its inputs are
  final bars only.
- Production row facts for the incident and its classification (9/9 post-deploy
  jobs split exactly by "end = today while the market is open") are recorded in
  issue #475.
