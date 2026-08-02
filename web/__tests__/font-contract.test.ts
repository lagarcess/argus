import { describe, expect, test } from "bun:test";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const webRoot = join(import.meta.dir, "..");
const layoutPath = join(webRoot, "app/layout.tsx");
const globalsPath = join(webRoot, "app/globals.css");
const fontsRoot = join(webRoot, "app/fonts");

function productionSourceFiles(root: string): string[] {
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const path = join(root, entry.name);
    if (entry.isDirectory()) return productionSourceFiles(path);
    return /\.(css|ts|tsx)$/.test(entry.name) ? [path] : [];
  });
}

describe("canonical offline typography contract", () => {
  test("does not import Google Fonts from production source", () => {
    const source = [
      ...productionSourceFiles(join(webRoot, "app")),
      ...productionSourceFiles(join(webRoot, "components")),
      ...productionSourceFiles(join(webRoot, "lib")),
    ]
      .map((path) => readFileSync(path, "utf8"))
      .join("\n");

    expect(source).not.toContain("next/font/google");
    expect(source).not.toContain("fonts.googleapis.com");
    expect(source).not.toContain("fonts.gstatic.com");
  });

  test("declares both canonical families through next/font/local", () => {
    const layout = readFileSync(layoutPath, "utf8");

    expect(layout).toContain('from "next/font/local"');
    expect(layout).toContain('src: "./fonts/InterVariable.woff2"');
    expect(layout).toContain('src: "./fonts/SpaceGrotesk[wght].woff2"');
    expect(layout).toContain('variable: "--font-inter"');
    expect(layout).toContain('variable: "--font-space-grotesk"');
    expect(layout).toContain('weight: "100 900"');
    expect(layout).toContain('weight: "300 700"');
  });

  test("keeps the existing CSS variable interface", () => {
    const globals = readFileSync(globalsPath, "utf8");

    expect(globals).toContain("--font-sans: var(--font-inter)");
    expect(globals).toContain("--font-display: var(--font-space-grotesk)");
  });

  test("includes font assets and visible license evidence", () => {
    for (const file of [
      "InterVariable.woff2",
      "SpaceGrotesk[wght].woff2",
      "OFL-1.1-Inter.txt",
      "OFL-1.1-Space-Grotesk.txt",
      "FONT-ATTRIBUTION.md",
    ]) {
      expect(statSync(join(fontsRoot, file)).isFile()).toBe(true);
    }

    expect(readFileSync(join(fontsRoot, "OFL-1.1-Inter.txt"), "utf8")).toContain(
      "SIL OPEN FONT LICENSE Version 1.1",
    );
    expect(readFileSync(join(fontsRoot, "OFL-1.1-Space-Grotesk.txt"), "utf8")).toContain(
      "SIL OPEN FONT LICENSE Version 1.1",
    );
    const attribution = readFileSync(join(fontsRoot, "FONT-ATTRIBUTION.md"), "utf8");
    expect(attribution).toContain("Inter 4.2");
    expect(attribution).toContain("Space Grotesk 2.0.0");
    expect(attribution).toContain("Copyright (c) 2016 The Inter Project Authors");
    expect(attribution).toContain("Copyright 2020 The Space Grotesk Project Authors");
  });
});
