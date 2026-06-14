import { describe, expect, test } from "bun:test";

import { cadenceDisplayLabel } from "../lib/cadence-display";

describe("cadence display labels", () => {
  test("renders canonical cadence values through localized copy", () => {
    const t = (key: string, fallback: string) =>
      key === "chat.cadence.weekly" ? "Semanal" : fallback;

    expect(cadenceDisplayLabel("weekly")).toBe("Weekly");
    expect(cadenceDisplayLabel("weekly", t)).toBe("Semanal");
  });

  test("keeps unknown cadence values as data instead of inventing prose", () => {
    expect(cadenceDisplayLabel("custom_interval")).toBe("custom_interval");
    expect(cadenceDisplayLabel(null)).toBeUndefined();
  });
});
