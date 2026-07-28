import { describe, expect, test } from "bun:test";

import {
  discoveryFreshnessDate,
  discoverySidecarFromMetadata,
  discoverySourceDomains,
} from "@/lib/chat-discovery-sidecar";
import { hydrateMessagesFromApi } from "@/components/chat/ChatInterface";
import type { ApiMessage } from "@/lib/chat-message-hydration";

function validSidecar(): Record<string, unknown> {
  return {
    schema_version: "argus_discovery/v1",
    kind: "asset_discovery",
    relationship: "category",
    query_summary: "cybersecurity stocks",
    retrieved_at: "2026-07-26T15:04:05Z",
    sources: [
      {
        title: "Cybersecurity leaders",
        domain: "example.com",
        url: "https://example.com/a",
        source_date: "2026-07-20",
      },
      {
        title: "Injected",
        domain: "evil.com",
        url: "javascript:alert(1)",
        source_date: null,
      },
    ],
    candidates: [
      {
        symbol: "CRWD",
        name: "CrowdStrike",
        asset_class: "equity",
        reason_text: "Named as a leading cybersecurity vendor.",
        source_indices: [0],
      },
      {
        symbol: "",
        name: "Malformed",
        asset_class: "equity",
        reason_text: "",
      },
      {
        symbol: "XX",
        name: "Wrong class",
        asset_class: "weird_class",
        reason_text: "",
      },
    ],
    unverified_names: ["Fake Private Co", "", 42],
  };
}

describe("discoverySidecarFromMetadata", () => {
  test("parses a valid sidecar and drops malformed entries", () => {
    const sidecar = discoverySidecarFromMetadata({ discovery: validSidecar() });
    expect(sidecar).not.toBeNull();
    expect(sidecar?.candidates.map((c) => c.symbol)).toEqual(["CRWD"]);
    expect(sidecar?.sources.map((s) => s.domain)).toEqual(["example.com"]);
    expect(sidecar?.unverified_names).toEqual(["Fake Private Co"]);
  });

  test("returns null without discovery metadata or valid candidates", () => {
    expect(discoverySidecarFromMetadata({})).toBeNull();
    expect(discoverySidecarFromMetadata(null)).toBeNull();
    const emptied = validSidecar();
    emptied.candidates = [];
    expect(discoverySidecarFromMetadata({ discovery: emptied })).toBeNull();
  });

  test("caps candidates and sources at contract bounds", () => {
    const wide = validSidecar();
    wide.candidates = Array.from({ length: 9 }, (_, index) => ({
      symbol: `S${index}`,
      name: `Name ${index}`,
      asset_class: "equity",
      reason_text: "",
    }));
    wide.sources = Array.from({ length: 9 }, (_, index) => ({
      title: `T${index}`,
      domain: `d${index}.com`,
      url: `https://d${index}.com/x`,
    }));
    const sidecar = discoverySidecarFromMetadata({ discovery: wide });
    expect(sidecar?.candidates).toHaveLength(5);
    expect(sidecar?.sources).toHaveLength(5);
  });

  test("can_request_search parses only an explicit backend true", () => {
    const granted = discoverySidecarFromMetadata({
      discovery: { ...validSidecar(), sources: [], can_request_search: true },
    });
    expect(granted?.can_request_search).toBe(true);

    const absent = discoverySidecarFromMetadata({
      discovery: validSidecar(),
    });
    expect(absent?.can_request_search).toBe(false);

    // A truthy non-boolean is not backend truth.
    const forged = discoverySidecarFromMetadata({
      discovery: { ...validSidecar(), can_request_search: "yes" },
    });
    expect(forged?.can_request_search).toBe(false);
  });

  test("rejects unknown kinds and relationships", () => {
    const wrongKind = { ...validSidecar(), kind: "news_feed" };
    expect(discoverySidecarFromMetadata({ discovery: wrongKind })).toBeNull();
    const wrongRel = { ...validSidecar(), relationship: "ranking" };
    expect(discoverySidecarFromMetadata({ discovery: wrongRel })).toBeNull();
  });
});

describe("discovery display helpers", () => {
  test("freshness date formats per locale from ISO", () => {
    const sidecar = discoverySidecarFromMetadata({ discovery: validSidecar() });
    expect(sidecar).not.toBeNull();
    if (!sidecar) return;
    expect(discoveryFreshnessDate(sidecar, "en-US")).toContain("2026");
    expect(discoveryFreshnessDate(sidecar, "es-419")).toContain("2026");
  });

  test("source domains dedupe in order", () => {
    const sidecar = discoverySidecarFromMetadata({ discovery: validSidecar() });
    expect(sidecar ? discoverySourceDomains(sidecar) : []).toEqual([
      "example.com",
    ]);
  });
});

describe("hydrateMessagesFromApi discovery attach", () => {
  const base = {
    conversation_id: "c1",
    created_at: "2026-07-26T15:05:00Z",
  };

  test("assistant message with discovery metadata hydrates the sidecar", () => {
    const items = [
      {
        ...base,
        id: "m1",
        role: "user",
        content: "What cybersecurity stocks could I test?",
        metadata: {},
      },
      {
        ...base,
        id: "m2",
        role: "assistant",
        content: "Here is what I verified.",
        metadata: { discovery: validSidecar() },
      },
    ] as unknown as ApiMessage[];
    const { messages } = hydrateMessagesFromApi(items);
    const assistant = messages.find((message) => message.id === "m2");
    expect(assistant?.discovery?.candidates.map((c) => c.symbol)).toEqual([
      "CRWD",
    ]);
  });

  test("legacy messages without discovery stay unchanged", () => {
    const items = [
      {
        ...base,
        id: "m3",
        role: "assistant",
        content: "Plain answer.",
        metadata: {},
      },
    ] as unknown as ApiMessage[];
    const { messages } = hydrateMessagesFromApi(items);
    expect(messages[0]?.discovery ?? null).toBeNull();
  });

  test("user messages never hydrate discovery", () => {
    const items = [
      {
        ...base,
        id: "m4",
        role: "user",
        content: "hello",
        metadata: { discovery: validSidecar() },
      },
    ] as unknown as ApiMessage[];
    const { messages } = hydrateMessagesFromApi(items);
    expect(messages[0]?.discovery ?? null).toBeNull();
  });
});
