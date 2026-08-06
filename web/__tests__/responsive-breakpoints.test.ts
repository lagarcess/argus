import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const globalsCss = readFileSync(
  join(import.meta.dir, "../app/globals.css"),
  "utf-8",
);

function declaredBreakpoints(): Record<string, string> {
  const entries: Record<string, string> = {};
  for (const line of globalsCss.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("--breakpoint-")) continue;
    const [name, value] = trimmed.replace(/;$/, "").split(":");
    entries[name.trim()] = value.trim();
  }
  return entries;
}

// DESIGN.md section 8: Mobile Small <400, Mobile 400-720, Tablet 720-1024,
// Desktop 1024-1280, Large 1280-1920. Values in rem at a 16px root.
const DESIGN_SCALE = {
  "--breakpoint-mobile": "25rem",
  "--breakpoint-tablet": "45rem",
  "--breakpoint-desktop": "64rem",
  "--breakpoint-large": "80rem",
  "--breakpoint-xlarge": "120rem",
} as const;

const LEGACY_ALIASES = {
  "--breakpoint-sm": "25rem",
  "--breakpoint-md": "45rem",
  "--breakpoint-lg": "64rem",
  "--breakpoint-xl": "80rem",
  "--breakpoint-2xl": "120rem",
} as const;

describe("responsive breakpoints", () => {
  test("clears the Tailwind default scale before declaring its own", () => {
    expect(globalsCss).toContain("--breakpoint-*: initial;");
  });

  test("declares the DESIGN.md section 8 scale", () => {
    const declared = declaredBreakpoints();
    for (const [name, value] of Object.entries(DESIGN_SCALE)) {
      expect(declared[name]).toBe(value);
    }
  });

  test("names the two thresholds the mobile spec sets", () => {
    const declared = declaredBreakpoints();
    expect(declared["--breakpoint-tablet"]).toBe("45rem");
    expect(declared["--breakpoint-desktop"]).toBe("64rem");
  });

  test("aliases the Tailwind default names position for position", () => {
    const declared = declaredBreakpoints();
    for (const [name, value] of Object.entries(LEGACY_ALIASES)) {
      expect(declared[name]).toBe(value);
    }
  });

  test("declares no breakpoint outside the DESIGN.md stops", () => {
    const allowed = new Set<string>([
      "--breakpoint-*",
      ...Object.keys(DESIGN_SCALE),
      ...Object.keys(LEGACY_ALIASES),
    ]);
    for (const name of Object.keys(declaredBreakpoints())) {
      expect(allowed.has(name)).toBe(true);
    }
  });

  test("keeps the desktop and large stops at their pre-migration widths", () => {
    // lg and xl were already 64rem and 80rem, so desktop markup cannot shift.
    const declared = declaredBreakpoints();
    expect(declared["--breakpoint-lg"]).toBe("64rem");
    expect(declared["--breakpoint-xl"]).toBe("80rem");
  });
});
