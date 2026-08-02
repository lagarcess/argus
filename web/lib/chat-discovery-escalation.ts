import type { DiscoverySidecar } from "@/components/chat/types";
import type { AssetClass } from "@/lib/argus-types";

type DiscoveryEscalationAssetKind = AssetClass | "asset";

const ASSET_KIND_KEYS = {
  equity: "chat.discovery_results.search_current_asset_equity",
  crypto: "chat.discovery_results.search_current_asset_crypto",
  currency_pair: "chat.discovery_results.search_current_asset_currency_pair",
  asset: "chat.discovery_results.search_current_asset_asset",
} as const;

const ASSET_KIND_DEFAULTS: Record<DiscoveryEscalationAssetKind, string> = {
  equity: "stocks",
  crypto: "cryptocurrencies",
  currency_pair: "currency pairs",
  asset: "assets",
};

const MESSAGE_DEFAULTS: Record<DiscoverySidecar["relationship"], string> = {
  category: "Search for current {{assetKind}} in {{query}}",
  peer: "Search for current {{assetKind}} similar to {{query}}",
  comparison: "Search for current {{assetKind}} comparable to {{query}}",
};

export type DiscoveryEscalationCopyPlan = {
  assetKindKey: (typeof ASSET_KIND_KEYS)[DiscoveryEscalationAssetKind];
  assetKindDefaultValue: string;
  messageKey: `chat.discovery_results.search_current_send_${DiscoverySidecar["relationship"]}`;
  messageDefaultValue: string;
  query: string;
};

export function discoveryEscalationCopyPlan(
  discovery: DiscoverySidecar,
): DiscoveryEscalationCopyPlan {
  const candidateClasses = new Set(
    discovery.candidates.map((candidate) => candidate.asset_class),
  );
  const assetKind: DiscoveryEscalationAssetKind =
    candidateClasses.size === 1
      ? (discovery.candidates[0]?.asset_class ?? "asset")
      : "asset";

  return {
    assetKindKey: ASSET_KIND_KEYS[assetKind],
    assetKindDefaultValue: ASSET_KIND_DEFAULTS[assetKind],
    messageKey: `chat.discovery_results.search_current_send_${discovery.relationship}`,
    messageDefaultValue: MESSAGE_DEFAULTS[discovery.relationship],
    query: discovery.query_summary,
  };
}
