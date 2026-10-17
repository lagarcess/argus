import { execFileSync } from "node:child_process";
import path from "node:path";

export const referenceRepositoryRoot = path.resolve(__dirname, "../..");

const definitions = [
  {
    name: "production-source", kind: "chat", port: 3200,
    sourceSha: "a9286b21886eb03df7a21f2f4b7d5e79af570679",
    webRoot: "/tmp/argus-web-production-reference-reviewed/web",
  },
  {
    name: "integration", kind: "chat", port: 3199,
    sourceSha: "c3b2042b9b69c5b75e173d145ed0020f00ccd79e",
    webRoot: "/tmp/argus-web-integration-reference-reviewed/web",
  },
  {
    name: "preview-current", kind: "preview", port: 3201,
    sourceSha: execFileSync("git", ["rev-parse", "HEAD"], { cwd: referenceRepositoryRoot, encoding: "utf8" }).trim(),
    webRoot: "/tmp/argus-web-current-preview-reference-reviewed/web",
  },
] as const;

// A reference origin is served only by the process Playwright launches from
// this same source root. Existing listeners fail the run instead of being used.
export const referenceManifest = definitions.map((definition) => {
  const hostname = "127.0.0.1";
  const origin = `http://${hostname}:${definition.port}`;
  return {
    ...definition,
    origin,
    webServer: {
      name: definition.name,
      command: `node node_modules/next/dist/bin/next dev --webpack --hostname ${hostname} --port ${definition.port}`,
      cwd: definition.webRoot,
      url: `${origin}${definition.kind === "chat" ? "/chat" : "/dev/ecosystem"}`,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "pipe" as const,
      stderr: "pipe" as const,
      env: {
        NEXT_DIST_DIR: ".next-reference",
        NEXT_TELEMETRY_DISABLED: "1",
        NEXT_PUBLIC_MOCK_AUTH: definition.kind === "chat" ? "true" : "false",
        NEXT_PUBLIC_ENABLE_SPANISH: "true",
        NEXT_PUBLIC_ARGUS_API_URL: "http://127.0.0.1:3999/api/v1",
      },
    },
  };
});

export type Reference = (typeof referenceManifest)[number];
