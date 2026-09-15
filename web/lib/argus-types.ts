export type AssetClass = "equity" | "crypto" | "currency_pair";

export type ConfirmationPeerIdentity = {
  symbol: string;
  asset_class: AssetClass;
};

export type ConfirmationPeerSelection =
  | { peers: ConfirmationPeerIdentity[] }
  | { symbols: string[] };
