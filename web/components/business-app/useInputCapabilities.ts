"use client";

import { useEffect, useState } from "react";

/**
 * What this browser can actually do for receipt intake. Measured from the
 * platform, never from screen width or the user agent, and without asking for
 * camera permission: device kinds are listed without labels until granted.
 */
export type InputCapabilities = Readonly<{
  /** `<input capture>` opens the camera directly on this device. */
  cameraCapture: boolean;
  /** A precise pointer, where dropping and pasting files is natural. */
  dropAndPaste: boolean;
}>;

const UNKNOWN: InputCapabilities = { cameraCapture: false, dropAndPaste: false };

export function useInputCapabilities(): InputCapabilities {
  const [capabilities, setCapabilities] = useState<InputCapabilities>(UNKNOWN);

  useEffect(() => {
    let cancelled = false;
    const finePointer = window.matchMedia?.("(any-pointer: fine)").matches ?? false;
    const supportsCaptureAttribute = "capture" in document.createElement("input");
    const coarsePointer = window.matchMedia?.("(any-pointer: coarse)").matches ?? false;
    const settle = (hasCamera: boolean) => {
      if (cancelled) return;
      setCapabilities({
        cameraCapture: hasCamera && supportsCaptureAttribute && coarsePointer,
        dropAndPaste: finePointer,
      });
    };
    const devices = navigator.mediaDevices?.enumerateDevices?.();
    if (!devices) {
      settle(false);
    } else {
      devices
        .then((list) => settle(list.some((device) => device.kind === "videoinput")))
        .catch(() => settle(false));
    }
    return () => {
      cancelled = true;
    };
  }, []);

  return capabilities;
}
