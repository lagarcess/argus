import type {
  ChatActionOption,
  ChatMention,
  DiscoveryCandidate,
  DiscoverySidecar,
  DiscoverySource,
} from "@/components/chat/types";

const ASSET_CLASSES = new Set(["equity", "crypto", "currency_pair"]);
const RELATIONSHIPS = new Set(["category", "peer", "comparison"]);
const MAX_SOURCES = 5;
const MAX_CANDIDATES = 5;
const MAX_UNVERIFIED = 3;

function stringOr(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function candidateOrNull(value: unknown): DiscoveryCandidate | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const symbol = stringOr(raw.symbol).trim();
  const assetClass = stringOr(raw.asset_class);
  if (!symbol || !ASSET_CLASSES.has(assetClass)) return null;
  return {
    symbol,
    name: stringOr(raw.name, symbol),
    asset_class: assetClass as DiscoveryCandidate["asset_class"],
    reason_text: stringOr(raw.reason_text),
    source_indices: Array.isArray(raw.source_indices)
      ? raw.source_indices.filter((index): index is number => typeof index === "number")
      : [],
  };
}

function sourceOrNull(value: unknown): DiscoverySource | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const domain = stringOr(raw.domain).trim();
  const url = stringOr(raw.url);
  if (!domain || !url.startsWith("https://")) return null;
  return {
    title: stringOr(raw.title),
    domain,
    url,
    source_date: typeof raw.source_date === "string" ? raw.source_date : null,
  };
}

/**
 * Validate one backend `discovery` metadata object into the typed sidecar.
 * The frontend renders backend truth only: anything malformed is dropped, and
 * a sidecar with zero valid candidates is treated as absent.
 */
export function discoverySidecarFromMetadata(
  metadata: Record<string, unknown> | null | undefined,
): DiscoverySidecar | null {
  const raw = metadata?.discovery;
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  if (record.kind !== "asset_discovery") return null;
  const relationship = stringOr(record.relationship);
  if (!RELATIONSHIPS.has(relationship)) return null;
  const candidates = (Array.isArray(record.candidates) ? record.candidates : [])
    .map(candidateOrNull)
    .filter((candidate): candidate is DiscoveryCandidate => candidate !== null)
    .slice(0, MAX_CANDIDATES);
  if (candidates.length === 0) return null;
  const sources = (Array.isArray(record.sources) ? record.sources : [])
    .map(sourceOrNull)
    .filter((source): source is DiscoverySource => source !== null)
    .slice(0, MAX_SOURCES);
  return {
    schema_version: stringOr(record.schema_version, "argus_discovery/v1"),
    kind: "asset_discovery",
    relationship: relationship as DiscoverySidecar["relationship"],
    query_summary: stringOr(record.query_summary),
    retrieved_at: stringOr(record.retrieved_at),
    sources,
    candidates,
    unverified_names: (Array.isArray(record.unverified_names)
      ? record.unverified_names
      : []
    )
      .filter((name): name is string => typeof name === "string" && name.trim() !== "")
      .slice(0, MAX_UNVERIFIED),
  };
}

/**
 * The asset identity for a tapped discovery candidate, as a mention.
 *
 * The candidate already passed `resolve_asset()` before it was allowed to
 * render, so re-deriving it from the four words of chip text throws away work
 * Argus already did — and gets it wrong, since "Backtest UNP" can read as a
 * strategy name. A mention is the channel `@ticker` already uses to say which
 * asset is meant, so identity travels without inventing a contract.
 *
 * This carries identity, never a prepared action: the turn still re-enters
 * interpretation and still requires confirmation before anything runs.
 */
export function discoveryCandidateMention(
  action: ChatActionOption,
): ChatMention | null {
  if (action.type !== "select_discovery_candidate") return null;
  const payload = action.payload ?? {};
  const symbol = typeof payload.symbol === "string" ? payload.symbol.trim() : "";
  if (!symbol) return null;
  const assetClass =
    typeof payload.asset_class === "string" &&
    ASSET_CLASSES.has(payload.asset_class)
      ? (payload.asset_class as DiscoveryCandidate["asset_class"])
      : null;
  const name = typeof payload.name === "string" ? payload.name.trim() : "";
  return {
    id: `discovery-candidate-${symbol}`,
    type: "asset",
    label: name || symbol,
    symbol,
    asset_class: assetClass,
    insert_text: symbol,
  };
}

/** Locale-formatted "as of" label from the sidecar's ISO timestamps. */
export function discoveryFreshnessDate(
  sidecar: DiscoverySidecar,
  locale: string,
): string {
  const raw = sidecar.retrieved_at;
  const parsed = raw ? new Date(raw) : null;
  if (!parsed || Number.isNaN(parsed.getTime())) return "";
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(parsed);
}

/** Compact unique source-domain list for the plain-text sources line. */
export function discoverySourceDomains(sidecar: DiscoverySidecar): string[] {
  const domains: string[] = [];
  for (const source of sidecar.sources) {
    if (!domains.includes(source.domain)) domains.push(source.domain);
  }
  return domains;
}
