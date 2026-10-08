import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");
const tiled = readFileSync(join(root, "app/icon.svg"), "utf8");
const light = readFileSync(join(root, "brand/cuadrao-mark-light.svg"), "utf8");
const paths = (svg: string) => [...svg.matchAll(/<path d="([^"]+)"/g)].map((match) => match[1]);

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
