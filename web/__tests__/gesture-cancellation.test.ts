import { describe, expect, test } from "bun:test";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

/**
 * A cancelled gesture is not a decision, on any surface that has one.
 *
 * `pointercancel` means the browser took the gesture away, most often because
 * it decided the movement was a scroll. It arrives carrying the last position,
 * so a handler that judges travel and velocity reads it as a deliberate
 * dismissal and closes the surface under the user's thumb.
 *
 * Both surfaces that drag had it wired to the same handler as `pointerup`. The
 * review found one; the other is the primitive underneath every sheet in the
 * app, which is why this is a sweep and not two fixes. A surface added later
 * gets the same answer without anyone having to remember the reason.
 */

const WEB_ROOT = join(import.meta.dir, "..");
const ROOTS = ["components", "app"];

function sourceFiles(dir: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry.startsWith(".")) continue;
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) {
      found.push(...sourceFiles(path));
      continue;
    }
    if (entry.endsWith(".tsx") || entry.endsWith(".ts")) found.push(path);
  }
  return found;
}

/** `onPointerCancel={foo}` -> `foo`, for each occurrence in the file. */
function handlerNames(source: string, prop: string): string[] {
  const pattern = new RegExp(`${prop}=\\{([A-Za-z0-9_.]+)\\}`, "g");
  return [...source.matchAll(pattern)].map((match) => match[1]);
}

describe("a cancelled pointer gesture decides nothing", () => {
  test("no surface hands pointercancel to its pointerup handler", () => {
    const offenders: string[] = [];
    for (const root of ROOTS) {
      for (const file of sourceFiles(join(WEB_ROOT, root))) {
        const source = readFileSync(file, "utf8");
        const cancels = handlerNames(source, "onPointerCancel");
        if (cancels.length === 0) continue;
        const ups = handlerNames(source, "onPointerUp");
        const shared = cancels.filter((name) => ups.includes(name));
        if (shared.length > 0) {
          offenders.push(`${relative(WEB_ROOT, file)}: ${shared.join(", ")}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  test("the sweep looks at the surfaces that actually drag", () => {
    // Without this the case above passes by finding nothing at all, which is
    // how a sweep quietly stops covering anything.
    const dragging = ROOTS.flatMap((root) =>
      sourceFiles(join(WEB_ROOT, root)).filter((file) =>
        readFileSync(file, "utf8").includes("onPointerCancel="),
      ),
    ).map((file) => relative(WEB_ROOT, file));

    expect(dragging).toContain("components/ui/BottomSheet.tsx");
    expect(dragging).toContain("components/sidebar/SidebarDrawer.tsx");
  });
});
