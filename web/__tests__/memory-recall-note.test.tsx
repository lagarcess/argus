import { describe, expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";

import { MemoryRecallDisclosure } from "../components/chat/MemoryRecallNote";
import type { MemoryRecallItem } from "../lib/memory-recalls";

const RECALLS: MemoryRecallItem[] = [
  {
    record_id: "record-1",
    label: "AAPL Buy and Hold: Rejected",
    value: "Rejected the higher drawdown Apple momentum variant.",
    category: "explicit_decision_note",
  },
];

function markup(open: boolean, recalls: MemoryRecallItem[] = RECALLS): string {
  return renderToStaticMarkup(
    <MemoryRecallDisclosure
      recalls={recalls}
      open={open}
      panelId="panel-1"
      onToggle={() => {}}
    />,
  );
}

describe("memory recall disclosure", () => {
  test("collapsed by default keeps the label and hides the memory", () => {
    const html = markup(false);

    expect(html).toContain("From your memory");
    expect(html).toContain('aria-expanded="false"');
    // The stamp stays in the tree for hydration but is closed to pointers,
    // assistive tech, and tab order.
    expect(html).toContain("grid-rows-[0fr]");
    expect(html).toContain('aria-hidden="true"');
    expect(html).toContain("inert=");
  });

  test("expanded reveals the stamp and reverses the affordance", () => {
    const html = markup(true);

    expect(html).toContain('aria-expanded="true"');
    expect(html).toContain("grid-rows-[1fr]");
    expect(html).toContain("AAPL Buy and Hold: Rejected");
    expect(html).toContain("Rejected the higher drawdown Apple momentum variant.");
    expect(html).toContain("Saved decisions you confirmed");
    expect(html).not.toContain("inert=");
  });

  test("the toggle word tracks the state", () => {
    expect(markup(false)).toContain(">Show<");
    expect(markup(true)).toContain(">Hide<");
  });

  test("the trigger controls the panel it owns", () => {
    const html = markup(false);

    expect(html).toContain('aria-controls="panel-1"');
    expect(html).toContain('id="panel-1"');
  });

  test("nothing renders without a recall", () => {
    expect(markup(false, [])).toBe("");
  });

  test("every recall is listed when open", () => {
    const html = markup(true, [
      ...RECALLS,
      {
        record_id: "record-2",
        label: "SPY benchmark preference",
        value: "Always compare equity ideas against SPY.",
        category: "explicit_decision_note",
      },
    ]);

    expect(html).toContain("AAPL Buy and Hold: Rejected");
    expect(html).toContain("SPY benchmark preference");
  });

  test("motion is opt-out for reduced-motion readers", () => {
    expect(markup(false)).toContain("motion-reduce:transition-none");
  });
});
