import type { TFunction } from "i18next";
import type { AssetClass } from "@/lib/argus-types";

const ASSET_CLASS_FALLBACKS: Record<AssetClass, string> = {
  equity: "Stocks",
  crypto: "Crypto",
  currency_pair: "Currency Pair",
};

export function assetClassDisplayLabel(
  assetClass: AssetClass | null | undefined,
  t?: TFunction,
) {
  if (!assetClass) return undefined;
  const fallback = ASSET_CLASS_FALLBACKS[assetClass];
  if (!fallback) return undefined;
  return t ? t(`chat.asset_class.${assetClass}`, fallback) : fallback;
}
