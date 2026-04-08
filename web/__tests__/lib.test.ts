import { describe, it, expect } from "bun:test";
import { isMockModeEnabled } from "../lib/mockApi";

describe("Mock API", () => {
  it("should have mock mode detection", () => {
    expect(typeof isMockModeEnabled).toBe("function");
  });

  it("should return a boolean from isMockModeEnabled", () => {
    const result = isMockModeEnabled();
    expect(typeof result).toBe("boolean");
  });
});
