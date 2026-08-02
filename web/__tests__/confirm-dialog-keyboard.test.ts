import { describe, expect, test } from "bun:test";

import { confirmDialogKeyboardAction } from "../components/ui/ConfirmDialog";

describe("ConfirmDialog keyboard policy", () => {
  test("keeps Escape as cancel for every invocation source", () => {
    expect(
      confirmDialogKeyboardAction({
        key: "Escape",
        isBusy: false,
        showKeyboardHints: false,
        targetIsButton: false,
      }),
    ).toBe("cancel");
  });

  test("confirms with Enter only for a keyboard-invoked idle dialog", () => {
    expect(
      confirmDialogKeyboardAction({
        key: "Enter",
        isBusy: false,
        showKeyboardHints: true,
        targetIsButton: false,
      }),
    ).toBe("confirm");
    expect(
      confirmDialogKeyboardAction({
        key: "Enter",
        isBusy: false,
        showKeyboardHints: false,
        targetIsButton: false,
      }),
    ).toBe("none");
  });

  test("does not override native Enter behavior on focused buttons", () => {
    expect(
      confirmDialogKeyboardAction({
        key: "Enter",
        isBusy: false,
        showKeyboardHints: true,
        targetIsButton: true,
      }),
    ).toBe("none");
    expect(
      confirmDialogKeyboardAction({
        key: "Enter",
        isBusy: true,
        showKeyboardHints: true,
        targetIsButton: false,
      }),
    ).toBe("none");
  });
});
