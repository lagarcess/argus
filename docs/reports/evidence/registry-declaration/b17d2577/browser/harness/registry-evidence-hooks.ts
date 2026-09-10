import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

const root = "/private/tmp/registry-declaration-browser-b17d2577";
const networkRoot = process.env.REGISTRY_NETWORK_DIR ?? path.join(root, "network");
const evidence = new Map<string, { requests: object[]; external: string[]; unhandledApi: string[]; pageErrors: string[] }>();
export function installRegistryEvidenceHooks() {
test.beforeEach(async ({ page }, info) => {
  const entry = { requests: [] as object[], external: [] as string[], unhandledApi: [] as string[], pageErrors: [] as string[] };
  evidence.set(info.testId, entry);
  page.on("request", request => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/v1/")) entry.requests.push({ method: request.method(), url: request.url() });
  });
  page.on("pageerror", error => entry.pageErrors.push(error.message));
  await page.routeWebSocket(/.*/, websocket => {
    const url = new URL(websocket.url());
    if (!["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)) {
      entry.external.push(url.origin + url.pathname);
      return websocket.close({ code: 1008, reason: "External network is forbidden in fixture evidence" });
    }
    websocket.connectToServer();
  });
  await page.route("**/*", route => {
    const url = new URL(route.request().url());
    if (!["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)) {
      entry.external.push(url.origin + url.pathname);
      return route.abort("blockedbyclient");
    }
    if (url.pathname.startsWith("/api/v1/")) {
      entry.unhandledApi.push(url.pathname);
      return route.abort("blockedbyclient");
    }
    return route.continue();
  });
});
test.afterEach(async ({}, info) => {
  const entry = evidence.get(info.testId)!;
  const name = info.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
  mkdirSync(networkRoot, { recursive: true });
  writeFileSync(path.join(networkRoot, `${name}.json`), JSON.stringify({ title: info.title, status: info.status, ...entry }, null, 2) + "\n");
  expect(entry.external, "No external request may escape the local fixture").toEqual([]);
  expect(entry.unhandledApi, "Every API request must have an authored response").toEqual([]);
  expect(entry.pageErrors).toEqual([]);
});
}
