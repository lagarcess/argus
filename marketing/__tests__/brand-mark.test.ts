import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");
const tiled = readFileSync(join(root, "app/icon.svg"), "utf8");
const light = readFileSync(join(root, "brand/cuadrao-mark-light.svg"), "utf8");
const paths = (svg: string) => [...svg.matchAll(/<path[^>]* d="([^"]+)"/g)].map((match) => match[1]);

// The light-background mark is the same geometry as the tiled icon without its tile.
describe("light-background mark", () => {
  test("draws the same three shapes as the tiled icon", () => {
    expect(paths(light)).toHaveLength(3);
    expect(paths(light)).toEqual(paths(tiled));
  });

  test("keeps the lean transform and omits the tile", () => {
    expect(light).toContain('transform="translate(6.8 0) skewX(-12)"');
    expect(light).not.toContain("<rect");
  });
});

const brand = (name: string) => readFileSync(join(root, "brand", name), "utf8");
const fills = (svg: string) => [...svg.matchAll(/stop-color="(#[0-9a-f]{6})"/g)].map((match) => match[1]);

describe("dark-background mark", () => {
  test("is the tiled icon's own shapes, transform and colours without the tile", () => {
    const dark = brand("cuadrao-mark-dark.svg");
    expect(paths(dark)).toEqual(paths(tiled));
    expect(fills(dark)).toEqual(fills(tiled));
    expect(dark).toContain('transform="translate(6.8 0) skewX(-12)"');
    expect(dark).not.toContain("<rect");
  });
});

describe("lockups", () => {
  test.each([
    ["cuadrao-lockup-light.svg", "cuadrao-mark-light.svg"],
    ["cuadrao-lockup-dark.svg", "cuadrao-mark-dark.svg"],
  ])("%s embeds the shapes of %s", (lockup, mark) => {
    expect(paths(brand(lockup)).slice(0, 3)).toEqual(paths(brand(mark)));
    expect(fills(brand(lockup))).toEqual(fills(brand(mark)));
  });

  test("the wordmark paths are the same letters in both colours", () => {
    const light = paths(brand("cuadrao-wordmark.svg"));
    expect(light).toHaveLength(1);
    expect(paths(brand("cuadrao-wordmark-dark.svg"))).toEqual(light);
    expect(paths(brand("cuadrao-lockup-light.svg")).at(-1)).toEqual(light[0]);
    expect(brand("cuadrao-wordmark.svg")).toContain('fill="#172b26"');
    expect(brand("cuadrao-wordmark-dark.svg")).toContain('fill="#fafbf8"');
  });
});

describe("wordmark specification", () => {
  test("states the styling the website's .wordmark rule uses", () => {
    const css = readFileSync(join(root, "components/business.module.css"), "utf8");
    const rule = css.match(/\n\.wordmark \{([^}]*)\}/)?.[1] ?? "";
    expect(rule).toMatch(/700 35px\/1 var\(--font-space-grotesk\)/);
    expect(rule).toContain("letter-spacing: -0.085em");
    const readme = brand("README.md");
    expect(readme).toContain("weight **700**");
    expect(readme).toContain("**-0.085em**");
  });
});
