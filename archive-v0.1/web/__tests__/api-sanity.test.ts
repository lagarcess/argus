import { describe, expect, it } from "bun:test";
import { postAuthSso, postTelemetryEvents } from "../lib/api/sdk.gen";

describe("generated API client sanity", () => {
  it("exposes narrow-MVP critical calls", () => {
    expect(typeof postAuthSso).toBe("function");
    expect(typeof postTelemetryEvents).toBe("function");
  });
});
