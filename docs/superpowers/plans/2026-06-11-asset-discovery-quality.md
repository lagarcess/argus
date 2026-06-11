# Asset Discovery Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make private-alpha `@` discovery rank provider-backed assets and runnable indicators more predictably while making repeated searches feel less jumpy.

**Architecture:** Keep the existing discovery architecture: `ChatInput` calls separate asset and indicator endpoints, `argus-api.ts` keeps a browser-session cache, FastAPI maps provider-backed domain search results into discovery response items, and selected mentions remain chat-request provenance only. Improve ranking and perceived speed inside those seams; do not add durable cache, schema, embeddings, or a second interpretation path.

**Tech Stack:** Next.js/React, Bun tests, FastAPI/Python, pytest, provider-backed asset catalog helpers.

---

## File Structure

- Modify `tests/section3/test_market_data_provider.py`
  - Adds provider-backed asset search expectations for common crypto-pair aliases.
- Modify `web/__tests__/chat-composer-display.test.ts`
  - Adds merge/ranking and loading-behavior guardrails for the composer picker.
- Modify `src/argus/domain/market_data/assets.py`
  - Adds provider-backed crypto name/pair aliases in `_add_aliases`.
- Modify `web/components/chat/ChatInput.tsx`
  - Refines discovery merge ranking and preserves visible results while a follow-up query is loading.

No API schema, Supabase schema, or chat runtime routing files should change.

---

### Task 1: Backend Provider-Backed Crypto Pair Aliases

**Files:**
- Modify: `tests/section3/test_market_data_provider.py`
- Modify: `src/argus/domain/market_data/assets.py`

- [ ] **Step 1: Write the failing backend test**

Append this test near the existing asset-search tests in `tests/section3/test_market_data_provider.py`:

```python
def test_asset_search_supports_provider_backed_crypto_name_pair_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assets.clear_asset_cache()
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")

    bitcoin_usd = assets.search_assets("bitcoin usd")
    bitcoin_dollar = assets.search_assets("bitcoin dollar")
    btc_usd = assets.search_assets("btc usd")

    assert bitcoin_usd[0].canonical_symbol == "BTC"
    assert bitcoin_dollar[0].canonical_symbol == "BTC"
    assert btc_usd[0].canonical_symbol == "BTC"
```

- [ ] **Step 2: Run the backend test to verify it fails**

Run:

```bash
poetry run pytest tests/section3/test_market_data_provider.py::test_asset_search_supports_provider_backed_crypto_name_pair_aliases -q
```

Expected: FAIL because `search_assets("bitcoin usd")`, `search_assets("bitcoin dollar")`, or `search_assets("btc usd")` returns no result before aliases are added.

- [ ] **Step 3: Add provider-backed crypto aliases**

In `src/argus/domain/market_data/assets.py`, update `_add_aliases` so crypto records add symbol/name USD aliases derived from the provider-backed record:

```python
    if record.asset_class == "crypto":
        base_name = record.name.lower().strip()
        base_aliases.add(f"{canonical}/USD")
        base_aliases.add(f"{canonical}USD")
        base_aliases.add(f"{canonical} USD")
        base_aliases.add(f"{canonical} dollar")
        if base_name:
            base_aliases.add(f"{base_name} usd")
            base_aliases.add(f"{base_name}/usd")
            base_aliases.add(f"{base_name} dollar")
```

Keep the existing alias loop unchanged so every alias maps to the same `ResolvedAsset`.

- [ ] **Step 4: Run the backend test to verify it passes**

Run:

```bash
poetry run pytest tests/section3/test_market_data_provider.py::test_asset_search_supports_provider_backed_crypto_name_pair_aliases -q
```

Expected: PASS.

---

### Task 2: Composer Discovery Ranking And Loading Behavior

**Files:**
- Modify: `web/__tests__/chat-composer-display.test.ts`
- Modify: `web/components/chat/ChatInput.tsx`

- [ ] **Step 1: Write failing frontend tests**

Add this test after `merges provider-backed asset and indicator results without tiny catalog caps` in `web/__tests__/chat-composer-display.test.ts`:

```typescript
  test("prioritizes a runnable indicator when the query matches its full name", () => {
    const assetResults: DiscoveryItem[] = [
      {
        id: "asset:equity:RELX",
        type: "asset",
        label: "RELX · Relx PLC",
        symbol: "RELX",
        asset_class: "equity",
        description: "Stock",
        insert_text: "RELX",
        provider: "alpaca",
        support_status: "supported",
      },
    ];
    const indicatorResults: DiscoveryItem[] = [
      {
        id: "indicator:rsi",
        type: "indicator",
        label: "RSI",
        symbol: "rsi",
        description: "Relative Strength Index",
        insert_text: "RSI",
        provider: "pandas-ta-classic",
        support_status: "supported",
      },
    ];

    const merged = mergeDiscoveryItems(
      assetResults,
      indicatorResults,
      "relative strength",
      DISCOVERY_SEARCH_LIMIT,
    );

    expect(merged.map((item) => item.id)).toEqual([
      "indicator:rsi",
      "asset:equity:RELX",
    ]);
  });
```

Add this test near the existing `chat input distinguishes discovery loading, empty, and unavailable states` test:

```typescript
  test("chat input preserves visible discovery results while a follow-up query loads", () => {
    const input = readFileSync(join(root, "components/chat/ChatInput.tsx"), "utf-8");

    expect(input).toContain('setDiscoveryStatus("loading")');
    expect(input).not.toContain('setDiscoveryItems([]);\n    setDiscoveryStatus("loading")');
  });
```

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run:

```bash
cd web && bun test __tests__/chat-composer-display.test.ts
```

Expected: FAIL because the current ranking does not use indicator descriptions for full-name matches and `ChatInput` clears discovery items immediately before loading.

- [ ] **Step 3: Implement ranking and loading fixes**

In `web/components/chat/ChatInput.tsx`, remove the non-empty query loading clear:

```typescript
    let cancelled = false;
    setDiscoveryStatus("loading");
```

Do not remove the empty-query `setDiscoveryItems([])` path.

Replace `rankDiscoveryItem` with a normalized ranking helper:

```typescript
function normalizeDiscoverySearchText(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function rankDiscoveryItem(item: DiscoveryItem, query: string) {
  const normalized = normalizeDiscoverySearchText(query);
  const symbol = normalizeDiscoverySearchText(item.symbol ?? "");
  const label = normalizeDiscoverySearchText(item.label);
  const description = normalizeDiscoverySearchText(item.description ?? "");
  const values = [symbol, label, description].filter(Boolean);
  const exact = values.some((value) => value === normalized);
  const prefix = values.some((value) => value.startsWith(normalized));
  const contained = values.some((value) => value.includes(normalized));
  if (exact && item.type === "indicator") return 0;
  if (exact) return 1;
  if (prefix && item.type === "asset") return 2;
  if (prefix) return 3;
  if (contained && item.type === "asset") return 4;
  if (contained) return 5;
  return item.type === "asset" ? 6 : 7;
}
```

Update the merge loop to compare the current asset and indicator ranks:

```typescript
    const indicatorRank = indicator ? rankDiscoveryItem(indicator, query) : Number.POSITIVE_INFINITY;
    const assetRank = asset ? rankDiscoveryItem(asset, query) : Number.POSITIVE_INFINITY;
    if (indicator && indicatorRank < assetRank) {
      push(indicator);
      push(asset);
    } else {
      push(asset);
      push(indicator);
    }
```

- [ ] **Step 4: Run the frontend tests to verify they pass**

Run:

```bash
cd web && bun test __tests__/chat-composer-display.test.ts
```

Expected: PASS.

---

### Task 3: Focused Verification And Commit

**Files:**
- Verify: `tests/section3/test_market_data_provider.py`
- Verify: `tests/test_chat_backtest_state_machine.py`
- Verify: `web/__tests__/chat-composer-display.test.ts`
- Verify: `web/__tests__/chat-composer-model.test.ts`
- Verify: `web/__tests__/argus-api-discovery-cache.test.ts`
- Verify: `web/__tests__/chat-discovery-panel.test.ts`

- [ ] **Step 1: Run focused backend discovery tests**

Run:

```bash
poetry run pytest tests/section3/test_market_data_provider.py::test_asset_search_supports_provider_backed_crypto_name_pair_aliases tests/section3/test_market_data_provider.py::test_asset_search_does_not_promote_close_symbol_typos_as_provider_truth tests/section3/test_market_data_provider.py::test_resolve_asset_does_not_force_ambiguous_company_hints tests/test_chat_backtest_state_machine.py::test_discovery_endpoints_return_assets_and_indicators tests/test_chat_backtest_state_machine.py::test_discovery_indicators_show_only_supported_indicators tests/test_chat_backtest_state_machine.py::test_discovery_assets_preserve_provider_source tests/test_chat_backtest_state_machine.py::test_discovery_assets_display_currency_pair_label -q
```

Expected: PASS. Existing Python dependency deprecation warnings are acceptable if tests pass.

- [ ] **Step 2: Run focused frontend discovery tests**

Run:

```bash
cd web && bun test __tests__/chat-composer-display.test.ts __tests__/chat-composer-model.test.ts __tests__/argus-api-discovery-cache.test.ts __tests__/chat-discovery-panel.test.ts
```

Expected: PASS.

- [ ] **Step 3: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 4: Commit implementation**

Run:

```bash
git add tests/section3/test_market_data_provider.py web/__tests__/chat-composer-display.test.ts src/argus/domain/market_data/assets.py web/components/chat/ChatInput.tsx
git commit -m "fix(chat): improve asset discovery quality"
```

Expected: commit succeeds with only the listed files staged.
