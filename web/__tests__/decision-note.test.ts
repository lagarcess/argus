import { describe, expect, test } from "bun:test";

import {
  DECISION_NOTE_MAX_LENGTH,
  decisionNoteCharacterCount,
  nextDecisionNoteValue,
} from "@/lib/decision-note";

describe("decision note authoring limit", () => {
  test("accepts 500 Unicode characters without treating emoji as two", () => {
    const note = "🙂".repeat(DECISION_NOTE_MAX_LENGTH);

    expect(decisionNoteCharacterCount(note)).toBe(500);
    expect(nextDecisionNoteValue("", note)).toBe(note);
  });

  test("clips new pasted text at 500 Unicode characters", () => {
    const accepted = "🙂".repeat(DECISION_NOTE_MAX_LENGTH);

    expect(nextDecisionNoteValue("", `${accepted}🙂`)).toBe(accepted);
  });

  test("rejects a middle insertion at capacity without deleting the tail", () => {
    const prefix = "a".repeat(250);
    const suffix = "b".repeat(250);
    const note = `${prefix}${suffix}`;

    expect(nextDecisionNoteValue(note, `${prefix}X${suffix}`)).toBe(note);
  });

  test("clips only inserted text while preserving an existing suffix", () => {
    const prefix = "a".repeat(249);
    const suffix = "b".repeat(249);

    expect(nextDecisionNoteValue(`${prefix}${suffix}`, `${prefix}XYZ${suffix}`)).toBe(
      `${prefix}XY${suffix}`,
    );
  });

  test("preserves a legacy long note while allowing only reductions", () => {
    const legacy = "🙂".repeat(501);
    const reduced = legacy.slice(0, -2);

    expect(nextDecisionNoteValue(legacy, `${legacy}x`)).toBe(legacy);
    expect(nextDecisionNoteValue(legacy, reduced)).toBe(reduced);
  });
});
