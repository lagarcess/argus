import { describe, expect, test } from "bun:test";

import {
  discoveryPanelDisplay,
  type DiscoverySearchStatus,
} from "../lib/chat-discovery-panel";

describe("chat discovery panel display", () => {
  test.each([
    [
      "idle",
      "",
      0,
      "chat.discovery.prompt",
      "Mention an asset or indicator",
      "chat.discovery.empty",
      "Type after @ to search supported assets and indicators.",
      false,
    ],
    [
      "loading",
      "nu",
      0,
      "chat.discovery.searching",
      "Searching supported assets...",
      "chat.discovery.loading",
      "Checking symbols, company names, crypto, currency pairs, and indicators.",
      true,
    ],
    [
      "empty",
      "nubank",
      0,
      "chat.discovery.no_results_title",
      "No supported matches",
      "chat.discovery.no_results",
      "No supported asset or indicator matched \"nubank\". Try a ticker or official company name.",
      false,
    ],
    [
      "error",
      "apple",
      0,
      "chat.discovery.unavailable_title",
      "Discovery is taking longer than expected",
      "chat.discovery.unavailable",
      "Try the ticker directly, or keep typing. Argus can still reason about your message.",
      false,
    ],
    [
      "ready",
      "apple",
      2,
      "chat.discovery.results",
      "Search results",
      "chat.discovery.empty",
      "Type after @ to search supported assets and indicators.",
      false,
    ],
  ] satisfies Array<
    [
      DiscoverySearchStatus,
      string,
      number,
      string,
      string,
      string,
      string,
      boolean,
    ]
  >)(
    "%s state returns explicit discovery panel copy",
    (
      status,
      query,
      itemCount,
      headerKey,
      headerFallback,
      bodyKey,
      bodyFallback,
      busy,
    ) => {
      expect(discoveryPanelDisplay({ itemCount, query, status })).toEqual({
        bodyFallback,
        bodyKey,
        bodyValues: query ? { query } : undefined,
        busy,
        headerFallback,
        headerKey,
        showBody: itemCount === 0,
      });
    },
  );
});
