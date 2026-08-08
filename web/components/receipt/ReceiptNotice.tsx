import type { ReceiptCopy } from "@/lib/receipt-copy";
import ProvenanceMark from "./ProvenanceMark";
import ReceiptViewBeacon from "./ReceiptViewBeacon";
import TryArgusCallToAction from "./TryArgusCallToAction";

type ReceiptNoticeProps = {
  kind: "revoked" | "unavailable";
  copy: ReceiptCopy;
};

/**
 * The tombstone, and its temporary sibling.
 *
 * A revoked receipt says plainly that it is gone rather than answering 404: the
 * person opening it already holds the link, so a not-found page only makes the
 * sender look careless. A backend that cannot answer right now is a separate
 * state, because telling someone their link is dead when it is not is a lie.
 *
 * Both still offer Try Argus. Someone who followed a link has already shown
 * intent.
 */
export default function ReceiptNotice({ kind, copy }: ReceiptNoticeProps) {
  const notice = kind === "revoked" ? copy.tombstone : copy.unavailable;

  return (
    <main className="mx-auto flex w-full max-w-[560px] flex-col gap-5 px-4 pb-14 pt-7 sm:px-6 sm:pt-10">
      <ReceiptViewBeacon />
      <div className="flex items-center justify-between gap-3">
        <span className="text-[11.5px] font-medium uppercase tracking-[0.07em] text-black/40 dark:text-white/40">
          {copy.eyebrow}
        </span>
        <ProvenanceMark label={copy.provenance} />
      </div>
      <section className="rounded-2xl border border-black/[0.08] px-4 py-5 dark:border-white/[0.10]">
        <h1 className="font-display text-[19px] font-semibold leading-tight text-black dark:text-white">
          {notice.title}
        </h1>
        <p className="mt-2 text-[13.5px] leading-relaxed text-black/60 dark:text-white/60">
          {notice.detail}
        </p>
        {kind === "revoked" && (
          <p className="mt-2 text-[13.5px] leading-relaxed text-black/60 dark:text-white/60">
            {copy.tombstone.cta_detail}
          </p>
        )}
      </section>
      <TryArgusCallToAction
        headline={copy.cta.headline}
        detail={copy.cta.detail}
        action={copy.cta.action}
      />
    </main>
  );
}
