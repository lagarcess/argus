export type DiscoverySearchStatus = "idle" | "loading" | "ready" | "empty" | "error";

export type DiscoveryPanelDisplay = {
  bodyFallback: string;
  bodyKey: string;
  bodyValues?: { query: string };
  busy: boolean;
  headerFallback: string;
  headerKey: string;
  showBody: boolean;
};

type DiscoveryPanelDisplayInput = {
  itemCount: number;
  query: string;
  status: DiscoverySearchStatus;
};

export function discoveryPanelDisplay({
  itemCount,
  query,
  status,
}: DiscoveryPanelDisplayInput): DiscoveryPanelDisplay {
  const normalizedQuery = query.trim();
  const bodyValues = normalizedQuery ? { query: normalizedQuery } : undefined;

  if (status === "loading") {
    return {
      bodyFallback: "Checking symbols, company names, crypto, currency pairs, and indicators.",
      bodyKey: "chat.discovery.loading",
      bodyValues,
      busy: true,
      headerFallback: "Searching supported assets...",
      headerKey: "chat.discovery.searching",
      showBody: itemCount === 0,
    };
  }

  if (status === "error") {
    return {
      bodyFallback: "Try the ticker directly, or keep typing. Argus can still reason about your message.",
      bodyKey: "chat.discovery.unavailable",
      bodyValues,
      busy: false,
      headerFallback: "Discovery is taking longer than expected",
      headerKey: "chat.discovery.unavailable_title",
      showBody: itemCount === 0,
    };
  }

  if (status === "empty") {
    return {
      bodyFallback: `No supported asset or indicator matched "${normalizedQuery}". Try a ticker or official company name.`,
      bodyKey: "chat.discovery.no_results",
      bodyValues,
      busy: false,
      headerFallback: "No supported matches",
      headerKey: "chat.discovery.no_results_title",
      showBody: itemCount === 0,
    };
  }

  if (status === "ready") {
    return {
      bodyFallback: "Type after @ to search supported assets and indicators.",
      bodyKey: "chat.discovery.empty",
      bodyValues,
      busy: false,
      headerFallback: "Search results",
      headerKey: "chat.discovery.results",
      showBody: itemCount === 0,
    };
  }

  return {
    bodyFallback: "Type after @ to search supported assets and indicators.",
    bodyKey: "chat.discovery.empty",
    bodyValues,
    busy: false,
    headerFallback: "Mention an asset or indicator",
    headerKey: "chat.discovery.prompt",
    showBody: itemCount === 0,
  };
}
