import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

describe("shared tooltip design system", () => {
  test("uses flat Argus styling and exposes tooltip semantics", () => {
    const tooltip = readFileSync(join(root, "components/ui/Tooltip.tsx"), "utf-8");

    expect(tooltip).toContain('role="tooltip"');
    expect(tooltip).toContain("id={tooltipId}");
    expect(tooltip).toContain("aria-describedby");
    expect(tooltip).not.toContain("shadow-[");
  });
});
