import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const webRoot = join(import.meta.dir, "..");

describe("guest modal viewport fit", () => {
  test("keeps feedback inside the dynamic viewport with a compact desktop cap", () => {
    const source = readFileSync(
      join(webRoot, "components/feedback/FeedbackDialog.tsx"),
      "utf8",
    );

    expect(source).toContain("p-3 sm:p-6");
    // Full height minus 12px read as a broken page rather than a dialog, and a
    // bug report is tall enough to hit the cap on every phone.
    expect(source).toContain("max-h-[88dvh]");
    expect(source).toContain("sm:max-h-[82dvh]");
    expect(source).toContain("flex-1 overflow-y-auto");
    // The actions are pinned outside the scrolling body, so a long form cannot
    // push Submit off the bottom of the screen.
    expect(source).toContain("flex shrink-0 justify-end gap-3 border-t");
    expect(source).toContain("form={formId}");
  });

  test("keeps both Omnisearch layouts inside a quieter viewport footprint", () => {
    const source = readFileSync(
      join(webRoot, "components/sidebar/ChatCommandPalette.tsx"),
      "utf8",
    );

    expect(source).toContain("p-3 sm:p-6");
    expect(source).toContain("max-h-[calc(100dvh-1.5rem)]");
    expect(source).toContain("h-[78dvh] w-[94vw] max-w-6xl");
    expect(source).toContain("h-[60dvh] w-full max-w-lg");
    expect(source).toContain("flex-1 overflow-y-auto");
  });
});
