import { describe, expect, test } from "bun:test";

import {
  confirmationRowKey,
  confirmationStatusFromLabel,
} from "../components/chat/confirmation-display";

describe("confirmation display labels", () => {
  test("legacy label lookup ignores prototype properties", () => {
    expect(confirmationStatusFromLabel("Ready to run")).toBe("ready_to_run");
    expect(confirmationStatusFromLabel("toString")).toBeNull();
    expect(confirmationRowKey({ label: "Assets" })).toBe("assets");
    expect(confirmationRowKey({ label: "toString" })).toBeNull();
  });
});
