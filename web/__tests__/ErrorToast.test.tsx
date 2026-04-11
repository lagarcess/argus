import { describe, it, expect, afterEach, mock, beforeEach } from "bun:test";
import { showErrorToast, ApiContractError } from "../components/ErrorToast";
import { toast } from "sonner";
import { Mock } from "bun:test";

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const mockToast = mock((_msg: string, _options?: unknown) => {});

// Mock sonner toast
mock.module("sonner", () => ({
  toast: mockToast,
}));

describe("showErrorToast", () => {
  beforeEach(() => {
    (toast as Mock<typeof toast>).mockClear();
  });

  afterEach(() => {
    mock.restore();
  });

  it("should handle standardized ApiContractError", () => {
    const error: ApiContractError = {
      error: "INVALID_REQUEST",
      message: "The request payload is invalid.",
      details: { field: "capital" },
    };

    showErrorToast(error);

    expect(toast).toHaveBeenCalledTimes(1);

    const callArgs = (toast as Mock<typeof toast>).mock.calls[0];
    expect(callArgs[0]).toBe("INVALID_REQUEST");
    expect(callArgs[1]?.description).toBe("The request payload is invalid.");
    expect(callArgs[1]?.className).toContain("bg-slate-900 border border-red-500/30");
    expect(callArgs[1]?.action?.label).toBe("Copy Details");

    // Test the clipboard copy action
    let clipboardText = "";
    Object.defineProperty(global.navigator, 'clipboard', {
      value: {
        writeText: (text: string) => { clipboardText = text; }
      },
      configurable: true
    });

    callArgs[1]?.action?.onClick();
    expect(clipboardText).toBe(JSON.stringify({ field: "capital" }));
  });

  it("should handle generic unknown errors", () => {
    const error = new Error("Something went completely wrong.");

    showErrorToast(error);

    expect(toast).toHaveBeenCalledTimes(1);
    const callArgs = (toast as Mock<typeof toast>).mock.calls[0];

    expect(callArgs[0]).toBe("UNKNOWN_ERROR");
    expect(callArgs[1]?.description).toBe("Something went completely wrong.");
  });

  it("should handle non-error objects (fallback)", () => {
    showErrorToast("Just a string error");

    expect(toast).toHaveBeenCalledTimes(1);
    const callArgs = (toast as Mock<typeof toast>).mock.calls[0];

    expect(callArgs[0]).toBe("UNKNOWN_ERROR");
    expect(callArgs[1]?.description).toBe("A critical system error occurred.");
  });
});
