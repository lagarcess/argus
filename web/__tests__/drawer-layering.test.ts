import { describe, expect, test } from "bun:test";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";

/**
 * Anything the drawer opens has to paint above the drawer.
 *
 * The drawer shipped at z-100 while every surface it hosts sits at 70 to 80,
 * so tapping Settings opened the profile menu underneath the panel that
 * launched it. Nothing looked broken: the menu mounted, its buttons were in the
 * DOM with real bounding boxes, and hit-testing found the drawer on top. Only a
 * human on a phone could see that the tap did nothing.
 *
 * Reviews do not catch this, because the two numbers live in different files
 * and neither is wrong on its own. So the ordering is asserted instead, over
 * whatever the drawer can actually reach.
 */

const WEB_ROOT = join(import.meta.dir, "..");
const DRAWER = "components/sidebar/SidebarDrawer.tsx";
/** The drawer takes its content as children, so the walk has to start there too. */
const DRAWER_CONTENT = "components/sidebar/ChatSidebar.tsx";

/** Every full-screen overlay a file declares. */
function overlayLayers(source: string): number[] {
  return [...source.matchAll(/fixed inset-0 z-\[(\d+)\]/g)].map((match) =>
    Number(match[1]),
  );
}

function resolveImport(fromFile: string, specifier: string): string | null {
  const base = specifier.startsWith("@/")
    ? join(WEB_ROOT, specifier.slice(2))
    : specifier.startsWith(".")
      ? resolve(dirname(fromFile), specifier)
      : null;
  if (!base) return null;
  for (const candidate of [
    `${base}.tsx`,
    `${base}.ts`,
    join(base, "index.tsx"),
    join(base, "index.ts"),
  ]) {
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

/** Everything the drawer can render, transitively. */
function drawerSubtree(): Map<string, string> {
  const found = new Map<string, string>();
  const queue = [join(WEB_ROOT, DRAWER), join(WEB_ROOT, DRAWER_CONTENT)];
  while (queue.length > 0) {
    const file = queue.pop()!;
    const key = relative(WEB_ROOT, file);
    if (found.has(key)) continue;
    const source = readFileSync(file, "utf-8");
    found.set(key, source);
    for (const match of source.matchAll(/from\s+"([^"]+)"/g)) {
      const next = resolveImport(file, match[1]);
      if (next) queue.push(next);
    }
  }
  return found;
}

const SUBTREE = drawerSubtree();
const DRAWER_LAYER = overlayLayers(SUBTREE.get(DRAWER)!)[0];

describe("drawer layering", () => {
  test("the walk reaches the surfaces the drawer actually opens", () => {
    // A silently empty graph would make every assertion below vacuous.
    expect(SUBTREE.has("components/sidebar/ProfileMenu.tsx")).toBe(true);
    expect(SUBTREE.has("components/settings/UsageModal.tsx")).toBe(true);
    expect(SUBTREE.size).toBeGreaterThan(20);
  });

  test("the drawer declares exactly one overlay layer", () => {
    expect(overlayLayers(SUBTREE.get(DRAWER)!)).toEqual([DRAWER_LAYER]);
  });

  test("every surface the drawer opens outranks the drawer", () => {
    const buried: string[] = [];
    for (const [path, source] of SUBTREE) {
      // The drawer and its own panel are the layer everything else clears.
      if (path === DRAWER || path === DRAWER_CONTENT) continue;
      for (const layer of overlayLayers(source)) {
        if (layer <= DRAWER_LAYER) buried.push(`${path} z-[${layer}]`);
      }
    }
    expect(buried).toEqual([]);
  });

  test("the drawer still covers the page it sits over", () => {
    // Lowering it to clear the dialogs must not drop it under chat chrome.
    const chrome = ["components/chat/ChatInterface.tsx"];
    for (const path of chrome) {
      const source = readFileSync(join(WEB_ROOT, path), "utf-8");
      for (const layer of overlayLayers(source)) {
        expect(layer).toBeLessThan(DRAWER_LAYER);
      }
    }
  });
});
