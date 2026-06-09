import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

describe("dev mode badge placement", () => {
  test("keeps mock auth controls away from chat header and composer hit targets", () => {
    const badge = readFileSync(join(root, "components/ui/DevModeBadge.tsx"), "utf-8");

    expect(badge).toContain('"use client";');
    expect(badge).toContain("useState");
    expect(badge).toContain("fixed right-4 top-24");
    expect(badge).toContain("aria-expanded={isOpen}");
    expect(badge).not.toContain("bottom-6 right-6");
    expect(badge).not.toContain("fixed top-4 right-4");
  });
});
