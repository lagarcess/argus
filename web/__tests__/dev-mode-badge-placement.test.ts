import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

describe("dev mode badge placement", () => {
  test("keeps mock auth controls away from the chat composer hit target", () => {
    const badge = readFileSync(join(root, "components/ui/DevModeBadge.tsx"), "utf-8");

    expect(badge).toContain("fixed top-4");
    expect(badge).not.toContain("bottom-6 right-6");
  });
});
