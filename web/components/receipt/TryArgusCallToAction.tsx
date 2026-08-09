"use client";

import Link from "next/link";
import { reportReceiptFunnelStage } from "@/lib/receipt-funnel";

type TryArgusCallToActionProps = {
  headline: string;
  detail: string;
  action: string;
};

/**
 * Lands on the standard guest entry with nothing carried across: no preloaded
 * question, no preloaded card, and no new query parameter on that surface. The
 * receipt already answered its own question, so replaying it would teach a
 * newcomer nothing and spend a guest run doing it.
 *
 * The funnel stage is recorded by a fire-and-forget beacon rather than a marker
 * in the URL, so the entry surface stays exactly as it is for everyone.
 */
export default function TryArgusCallToAction({
  headline,
  detail,
  action,
}: TryArgusCallToActionProps) {
  return (
    <section className="mt-12">
      <h2 className="font-display text-[24px] font-medium leading-tight tracking-[-0.4px] text-white">
        {headline}
      </h2>
      <p className="mt-2 max-w-[46ch] text-[14px] leading-relaxed text-white/55">
        {detail}
      </p>
      <Link
        href="/"
        onClick={() => reportReceiptFunnelStage("try_argus")}
        className="font-display mt-5 inline-flex min-h-[52px] w-full items-center justify-center rounded-full bg-white px-8 text-[16px] font-medium text-[#191c1f] transition-colors hover:bg-white/90 sm:w-auto"
      >
        {action}
      </Link>
    </section>
  );
}
