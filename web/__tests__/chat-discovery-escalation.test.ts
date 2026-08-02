import { describe, expect, test } from "bun:test";
import { createInstance } from "i18next";

import {
  discoveryEscalationCopyPlan,
  type DiscoveryEscalationCopyPlan,
} from "@/lib/chat-discovery-escalation";
import type {
  DiscoveryCandidate,
  DiscoverySidecar,
} from "@/components/chat/types";
import en from "../public/locales/en/common.json";
import es419 from "../public/locales/es-419/common.json";

const candidate = (
  assetClass: DiscoveryCandidate["asset_class"],
): DiscoveryCandidate => ({
  symbol: assetClass === "crypto" ? "BTC" : assetClass === "currency_pair" ? "EURUSD" : "PFE",
  name: "Candidate",
  asset_class: assetClass,
  reason_text: "Resolver-verified candidate",
  source_indices: [],
});

const sidecar = (
  candidates: DiscoveryCandidate[],
  relationship: DiscoverySidecar["relationship"] = "category",
  querySummary = "the pharmaceutical sector",
): DiscoverySidecar => ({
  schema_version: "argus_discovery/v1",
  kind: "asset_discovery",
  relationship,
  query_summary: querySummary,
  retrieved_at: "2026-08-02T00:00:00Z",
  sources: [],
  candidates,
  unverified_names: [],
  can_request_search: true,
});

async function translate(
  resources: Record<string, unknown>,
  plan: DiscoveryEscalationCopyPlan,
) {
  const instance = createInstance();
  await instance.init({
    lng: "test",
    fallbackLng: false,
    resources: { test: { translation: resources } },
    interpolation: { escapeValue: false },
  });
  const assetKind = instance.t(plan.assetKindKey);
  return instance.t(plan.messageKey, {
    query: plan.query,
    assetKind,
  });
}

describe("grounded-discovery escalation copy", () => {
  test.each([
    ["equity", "chat.discovery_results.search_current_asset_equity"],
    ["crypto", "chat.discovery_results.search_current_asset_crypto"],
    ["currency_pair", "chat.discovery_results.search_current_asset_currency_pair"],
  ] as const)("uses the %s noun for a uniform candidate set", (assetClass, key) => {
    expect(
      discoveryEscalationCopyPlan(
        sidecar([candidate(assetClass), candidate(assetClass)]),
      ).assetKindKey,
    ).toBe(key);
  });

  test("uses the generic asset noun for mixed or empty candidate sets", () => {
    for (const candidates of [
      [],
      [candidate("equity"), candidate("crypto")],
    ]) {
      expect(discoveryEscalationCopyPlan(sidecar(candidates)).assetKindKey).toBe(
        "chat.discovery_results.search_current_asset_asset",
      );
    }
  });

  test.each(["category", "peer", "comparison"] as const)(
    "uses the %s relationship template",
    (relationship) => {
      expect(
        discoveryEscalationCopyPlan(
          sidecar([candidate("equity")], relationship),
        ).messageKey,
      ).toBe(`chat.discovery_results.search_current_send_${relationship}`);
    },
  );

  test("emits semantic English and es-419 natural-language turns", async () => {
    const englishPlan = discoveryEscalationCopyPlan(
      sidecar([candidate("equity")]),
    );
    const spanishPlan = discoveryEscalationCopyPlan(
      sidecar([candidate("equity")], "category", "el sector farmacéutico"),
    );

    expect(await translate(en, englishPlan)).toBe(
      "Search for current stocks in the pharmaceutical sector",
    );
    expect(await translate(es419, spanishPlan)).toBe(
      "Buscar acciones actuales en el sector farmacéutico",
    );
  });

  test("every escalation key exists in both locale catalogs", () => {
    const keys = [
      "search_current_asset_equity",
      "search_current_asset_crypto",
      "search_current_asset_currency_pair",
      "search_current_asset_asset",
      "search_current_send_category",
      "search_current_send_peer",
      "search_current_send_comparison",
    ] as const;

    for (const key of keys) {
      expect(en.chat.discovery_results[key]).toBeTruthy();
      expect(es419.chat.discovery_results[key]).toBeTruthy();
    }
  });
});
