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
    <section className="rounded-2xl border border-black/[0.08] bg-black/[0.02] px-4 py-5 dark:border-white/[0.10] dark:bg-white/[0.03]">
      <h2 className="font-display text-[16px] font-semibold text-black dark:text-white">
        {headline}
      </h2>
      <p className="mt-1.5 text-[13.5px] leading-relaxed text-black/55 dark:text-white/55">
        {detail}
      </p>
      <Link
        href="/"
        onClick={() => reportReceiptFunnelStage("try_argus")}
        className="mt-4 inline-flex min-h-11 w-full items-center justify-center rounded-full bg-[#191c1f] px-5 text-[14px] font-medium text-white transition-colors hover:bg-black dark:bg-white dark:text-[#191c1f] dark:hover:bg-white/90"
      >
        {action}
      </Link>
    </section>
  );
}
