# Argus calculation core reuse review

## Findings

### [P1] Use the money app's rounding rule for currency presentation

**Location:** `money-view/server/argus_core/calculations/_shared.py:112-118,246-248`; coverage at `money-view/tests/test_argus_core_reuse.py:189-208`.

`money_round()` uses Python `round(float, digits)`, which applies ties-to-even to a binary float. The rest of the money app rounds presentation and settlement with `Decimal.quantize(..., ROUND_HALF_UP)`, and the browser's `Intl.NumberFormat` also expands half values. This is reachable through every calculation presenter that calls `money_fact()` and through the newly adapted ranked/scenario money rows. A valid `income_yield` calculation with `JPY`, annual income `1`, and yield `40%` computes a price of `2.5`; the card stores and displays `JPY 2`, while the money app/browser display rule yields `JPY 3`. Likewise, `KWD 1.2345` becomes `1.234` instead of `1.235`. The analytical result remains correct, but the user-visible typed fact is wrong by one minor unit.

The existing test values (`33.0`, `33.333`) avoid the half-unit boundary, so the 18 passing tests do not detect this. The smallest safe fix is to make `money_round()` convert through `Decimal(str(value))` and quantize to `CURRENCY_DIGITS[currency]` with `ROUND_HALF_UP`, then convert the presentation value back to the contract's numeric type. The same helper should continue to own money facts, repairs, ranked money rows, and valuation scenarios. Add JPY `2.5 -> 3` and KWD `1.2345 -> 1.235` regression cases.

### [P2] Make the reused core derive from one executable source

**Location:** `money-view/docs/experience/CORE_REUSE.md:64-129`; active import path `money-view/server/platform/chat.py:19-21`.

The package copies 29 Python files and 4,305 lines covering `ToolDeclaration`, tool contracts, all 11 calculation declarations, and the full finance math closure. The original Argus owner remains active under `src/argus/domain`, so there are now two executable implementations of the same capability. The pinned source hashes accurately describe today's copy, but no build or test derives the local package from those sources or prevents a future Argus correctness fix from landing in only one runtime. Because chat already imports `server.argus_core`, that divergence is reachable rather than archival. This conflicts with the repository's founder-locked rule that duplicated facts must have one owner from which every consumer derives.

The smallest safe shape is a generated/versioned package whose build input is the canonical Argus core and whose local layer supplies only the documented adapters: the reduced `ResearchSource`, local currency catalog, account/record provenance, and presentation rounding. Generated files should reject hand edits and be reproducible from the pinned source revision. Preferably, split those few dependency seams into neutral canonical modules and import the core directly. The current documentation and manifest should remain as provenance evidence, but they cannot be the synchronization mechanism.

## Verified clean surfaces

- The manifest contains 33 entries and every packaged file matches its recorded SHA-256.
- The documented base SHA exists, and the source hashes for `tool_declaration.py`, `tool_contracts.py`, research contracts, the calculations manifest, and the finance manifest match that base.
- After namespace normalization, finance algorithms and declaration behavior match the pinned Argus source; the only material differences are the documented currency/provenance adaptations.
- Unknown selection and recomputation behavior remain intact: edits preserve the selected unknown and re-source changed fields as user-provided.
- Account/record sources require a date, reference, and ISO-shaped currency; cross-currency composition fails validation. The calculation core does not perform conversion or ledger writes.
- `ToolResultCard` retains call identity, artifact identity, arguments with provenance, validated outcome, presentation, and input revision exactly as the Argus contract does.
- The import graph has no dotenv, OpenRouter, HTTP client, Supabase, production `argus.domain`, or network dependency. The local `platform.common` import supplies the canonical supported-currency digit table and has no import-time store initialization.
- The reported focused verification is 18 passing tests. I did not use network access or live models. I additionally reproduced the two rounding failures above with the packaged code and compared them with `Intl.NumberFormat` and the money app's `ROUND_HALF_UP` owner.

## Scope

No application, Git, environment, Supabase, production, or deployment state was changed. This review wrote only this report.

## Fix delta verdict

### P1 closed: one HALF_UP owner now reaches every money presentation

The generated `_shared.money_round()` converts through `Decimal(str(value))` and quantizes with `ROUND_HALF_UP` using the shared `CURRENCY_DIGITS` owner. Ordinary answers reach it through `money_fact`; the only repair that carries money passes its currency into `no_solution`; ranked money values and gaps call it through `display_value`; and valuation scenario base values, row values, and prices call it directly. The regression cases cover JPY and KWD half units, including positive and negative values in the repair and ranked paths. The focused suite passes: `26 passed in 0.66s`. The committed package also passes `scripts/sync_argus_core.py --check`, reporting 28 verified generated files.

### [P2] Reject unexpected executable files in the generated package

**Location:** `money-view/scripts/sync_argus_core.py:400-417`; coverage at `money-view/tests/test_argus_core_reuse.py:430-467`.

The generator now correctly pins every selected canonical source hash, applies named one-seam adapters, writes source and output hashes, and rejects missing or edited expected files. That makes the checked files derived artifacts rather than a second hand-maintained finance implementation. The current package contains no unexpected Python source beyond the two documented local files, `__init__.py` and `research_contracts.py`.

The check is not fully fail closed yet because it only iterates over expected generated paths. I generated a clean temporary package, added an importable `rogue_finance.py`, and reran `--check`; it still returned 0 and reported all 28 files verified. The same behavior would leave a stale module behind if a selected canonical file were later removed or renamed, since `--write` also only overwrites expected paths. Such a file can be imported from the active package and become another executable owner without invalidating the advertised check.

The smallest safe fix is for `--check` to compare the recursive Python-file inventory with the generated paths plus an explicit allowlist for the two hand-maintained local files, ignoring cache artifacts, and fail with the unexpected paths. Add the temporary-output case above as a regression test. `--write` can leave deletion manual; a following check must fail until the stale file is reviewed and removed.

With that inventory gap fixed, P2 is closed on the reviewed shape. I found no other reachable issue or unjustified complexity in the fix delta. I did not use network access or live models, and made no application, canonical Argus source, Git, environment, Supabase, or deployment change.

## Latest inventory-check verdict

P2 is closed. `_check()` now compares the full recursive non-cache file inventory with the 28 generated outputs plus the explicit root `__init__.py` and `research_contracts.py` adapters. It rejects an unexpected root module, a stale generated module, or an extra file inside a namespace package. For the committed default package it also fails if either named local adapter is missing. This keeps the canonical Argus files as the finance source owner while making the copied runtime a reproducible derived artifact with two narrow, visible local seams.

The temporary-output regression writes `rogue_finance.py` and requires both a nonzero result and `unexpected:rogue_finance.py`; after removing it, the existing byte-level hand-edit case still verifies generated content drift. I reran the focused evidence: `26 passed in 0.68s`, and the committed generator check reported 28 verified files. No findings remain in this latest delta. I made no code, network, provider, Git, environment, Supabase, or deployment change.
