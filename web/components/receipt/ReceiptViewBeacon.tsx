"use client";

import { useEffect, useRef } from "react";
import { reportReceiptFunnelStage } from "@/lib/receipt-funnel";

/**
 * Reports one view, once, from the rendered page.
 *
 * View counting cannot live on the read endpoint: that endpoint answers the page's
 * metadata pass, the page render, and the preview image, so a link pasted into a
 * chat would log several views before any person opened it. Reporting from here
 * means a view is a real browser that actually rendered the receipt.
 */
export default function ReceiptViewBeacon() {
  const reported = useRef(false);

  useEffect(() => {
    if (reported.current) return;
    reported.current = true;
    reportReceiptFunnelStage("viewed");
  }, []);

  return null;
}
